"""LLM key resolution by deployment mode (ADR-007) — no live LLM calls.

byo tests are async: each pytest-asyncio test runs in its own task, so
ContextVar writes cannot leak between tests.
"""

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from jobcopilot_agent.config import settings
from jobcopilot_agent.deps import provision_llm_key
from jobcopilot_agent.services import llm
from jobcopilot_agent.services.llm import get_llm, get_vision_llm, set_request_llm_key
from jobcopilot_shared.exceptions import LLMKeyNotConfiguredError
from langchain_openai import ChatOpenAI
from pydantic import SecretStr


@pytest.fixture(autouse=True)
def _fresh_model_cache() -> Iterator[None]:
    llm._chat_model.cache_clear()
    yield
    llm._chat_model.cache_clear()


def _key(model: ChatOpenAI) -> str:
    assert isinstance(model.openai_api_key, SecretStr)
    return model.openai_api_key.get_secret_value()


def test_platform_mode_uses_env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_key_mode", "platform")
    monkeypatch.setattr(settings, "dashscope_api_key", "sk-platform")
    assert _key(get_llm()) == "sk-platform"
    assert _key(get_vision_llm()) == "sk-platform"


@pytest.mark.asyncio
async def test_byo_mode_uses_request_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_key_mode", "byo")
    monkeypatch.setattr(settings, "dashscope_api_key", "sk-platform")
    set_request_llm_key("sk-user")
    assert _key(get_llm()) == "sk-user"
    assert _key(get_vision_llm()) == "sk-user"


@pytest.mark.asyncio
async def test_byo_mode_without_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_key_mode", "byo")
    with pytest.raises(LLMKeyNotConfiguredError):
        get_llm()


@pytest.mark.asyncio
async def test_byo_mode_caches_models_per_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_key_mode", "byo")
    set_request_llm_key("sk-user-a")
    model_a = get_llm()
    set_request_llm_key("sk-user-b")
    model_b = get_llm()
    assert model_a is not model_b
    set_request_llm_key("sk-user-a")
    assert get_llm() is model_a


@pytest.mark.asyncio
async def test_provision_dependency_binds_stored_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_key_mode", "byo")
    with patch(
        "jobcopilot_agent.deps.fetch_user_llm_key",
        new_callable=AsyncMock,
        return_value="sk-stored",
    ):
        await provision_llm_key({"user_id": "u1", "tenant_id": "t1"})
    assert _key(get_llm()) == "sk-stored"


@pytest.mark.asyncio
async def test_provision_dependency_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_key_mode", "byo")
    with (
        patch(
            "jobcopilot_agent.deps.fetch_user_llm_key",
            new_callable=AsyncMock,
            return_value=None,
        ),
        pytest.raises(LLMKeyNotConfiguredError),
    ):
        await provision_llm_key({"user_id": "u1", "tenant_id": "t1"})


@pytest.mark.asyncio
async def test_provision_dependency_skips_key_fetch_in_platform_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Platform mode never fetches a per-user key (quota check mocked — no live Redis)."""
    monkeypatch.setattr(settings, "llm_key_mode", "platform")
    with (
        patch("jobcopilot_agent.deps.fetch_user_llm_key", new_callable=AsyncMock) as fetch,
        patch("jobcopilot_agent.deps.enforce_daily_quota", new_callable=AsyncMock),
    ):
        await provision_llm_key({"user_id": "u1", "tenant_id": "t1"})
    fetch.assert_not_awaited()
