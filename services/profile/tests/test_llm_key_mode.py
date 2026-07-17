"""Profile-side behavior of the LLM key deployment modes (ADR-007)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from jobcopilot_profile.config import settings
from jobcopilot_profile.routers.profiles import update_credentials
from jobcopilot_profile.schemas.profile import CredentialsUpdate
from jobcopilot_profile.services.embedding import embed_and_upsert, resolve_embedding_api_key
from jobcopilot_shared.crypto import decrypt, encrypt
from jobcopilot_shared.exceptions import NotFoundError, PermissionDeniedError

_USER = uuid.uuid4()


@pytest.mark.asyncio
async def test_update_credentials_encryptor_round_trips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: the router passed the raw 2-arg encrypt() to the repo, which
    calls it with one arg — saving a key 500'd (TypeError) since launch."""
    monkeypatch.setattr(settings, "llm_key_mode", "byo")
    with (
        patch(
            "jobcopilot_profile.repositories.profile_repo.ProfileRepository.update_credentials",
            new_callable=AsyncMock,
        ) as update,
        patch(
            "jobcopilot_profile.routers.profiles.validate_llm_key",
            new_callable=AsyncMock,
        ),
    ):
        await update_credentials(
            CredentialsUpdate(llm_api_key="sk-round-trip"),
            session=AsyncMock(),
            tenant_id=_USER,
            user_id=_USER,
        )
    assert update.await_args is not None
    encryptor = update.await_args.args[2]
    assert decrypt(encryptor("sk-round-trip"), settings.encryption_key) == "sk-round-trip"


@pytest.mark.asyncio
async def test_update_credentials_rejected_in_platform_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_key_mode", "platform")
    with pytest.raises(PermissionDeniedError):
        await update_credentials(
            CredentialsUpdate(llm_api_key="sk-user"),
            session=AsyncMock(),
            tenant_id=_USER,
            user_id=_USER,
        )


@pytest.mark.asyncio
async def test_resolve_key_platform_mode_uses_env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_key_mode", "platform")
    monkeypatch.setattr(settings, "dashscope_api_key", "sk-platform")
    assert await resolve_embedding_api_key(AsyncMock(), _USER) == "sk-platform"


@pytest.mark.asyncio
async def test_resolve_key_byo_mode_decrypts_user_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_key_mode", "byo")
    profile = AsyncMock()
    profile.llm_api_key_enc = encrypt("sk-user", settings.encryption_key)
    with patch(
        "jobcopilot_profile.repositories.profile_repo.ProfileRepository.get_by_user",
        new_callable=AsyncMock,
        return_value=profile,
    ):
        assert await resolve_embedding_api_key(AsyncMock(), _USER) == "sk-user"


@pytest.mark.asyncio
async def test_resolve_key_byo_mode_without_profile_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_key_mode", "byo")
    with patch(
        "jobcopilot_profile.repositories.profile_repo.ProfileRepository.get_by_user",
        new_callable=AsyncMock,
        side_effect=NotFoundError("no profile"),
    ):
        assert await resolve_embedding_api_key(AsyncMock(), _USER) is None


@pytest.mark.asyncio
async def test_embed_skips_without_key() -> None:
    assert await embed_and_upsert(uuid.uuid4(), _USER, "resume text", None) is False
