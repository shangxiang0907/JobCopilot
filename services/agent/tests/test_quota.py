"""Per-tenant daily AI quota (platform mode) — no live Redis, no live LLM calls."""

from unittest.mock import AsyncMock, patch

import pytest
from jobcopilot_agent.config import settings
from jobcopilot_agent.deps import provision_llm_key
from jobcopilot_agent.services import quota
from jobcopilot_agent.services.quota import enforce_daily_quota
from jobcopilot_shared.exceptions import QuotaExceededError, QuotaUnavailableError


def _redis_mock(incr_result: int) -> AsyncMock:
    redis = AsyncMock()
    redis.incr.return_value = incr_result
    return redis


@pytest.mark.asyncio
async def test_under_quota_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_daily_quota", 20)
    with patch.object(quota, "_redis", _redis_mock(incr_result=20)):
        await enforce_daily_quota("t1")


@pytest.mark.asyncio
async def test_over_quota_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_daily_quota", 20)
    with (
        patch.object(quota, "_redis", _redis_mock(incr_result=21)),
        pytest.raises(QuotaExceededError),
    ):
        await enforce_daily_quota("t1")


@pytest.mark.asyncio
async def test_first_action_sets_key_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_daily_quota", 20)
    redis = _redis_mock(incr_result=1)
    with patch.object(quota, "_redis", redis):
        await enforce_daily_quota("t1")
    redis.expire.assert_awaited_once()


@pytest.mark.asyncio
async def test_nonpositive_quota_disables_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_daily_quota", 0)
    redis = _redis_mock(incr_result=999)
    with patch.object(quota, "_redis", redis):
        await enforce_daily_quota("t1")
    redis.incr.assert_not_awaited()


@pytest.mark.asyncio
async def test_redis_down_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cost enforcement, not traffic smoothing: no counting means no spend (503)."""
    monkeypatch.setattr(settings, "llm_daily_quota", 20)
    redis = AsyncMock()
    redis.incr.side_effect = ConnectionError("redis unreachable")
    with patch.object(quota, "_redis", redis), pytest.raises(QuotaUnavailableError):
        await enforce_daily_quota("t1")


@pytest.mark.asyncio
async def test_quota_keys_are_per_tenant_per_day(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_daily_quota", 20)
    redis = _redis_mock(incr_result=2)
    with patch.object(quota, "_redis", redis):
        await enforce_daily_quota("tenant-a")
        await enforce_daily_quota("tenant-b")
    keys = [call.args[0] for call in redis.incr.await_args_list]
    assert keys[0] != keys[1]
    assert all(k.startswith("quota:llm:tenant-") for k in keys)


@pytest.mark.asyncio
async def test_platform_mode_chokepoint_enforces_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_key_mode", "platform")
    with patch("jobcopilot_agent.deps.enforce_daily_quota", new_callable=AsyncMock) as enforce:
        await provision_llm_key({"user_id": "u1", "tenant_id": "t1"})
    enforce.assert_awaited_once_with("t1")


@pytest.mark.asyncio
async def test_byo_mode_is_not_quota_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_key_mode", "byo")
    with (
        patch("jobcopilot_agent.deps.enforce_daily_quota", new_callable=AsyncMock) as enforce,
        patch(
            "jobcopilot_agent.deps.fetch_user_llm_key",
            new_callable=AsyncMock,
            return_value="sk-user",
        ),
    ):
        await provision_llm_key({"user_id": "u1", "tenant_id": "t1"})
    enforce.assert_not_awaited()
