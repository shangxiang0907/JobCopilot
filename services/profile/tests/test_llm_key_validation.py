"""BYO key validation at save time — provider calls are mocked, never live."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from jobcopilot_profile.config import settings
from jobcopilot_profile.routers.profiles import update_credentials
from jobcopilot_profile.schemas.profile import CredentialsUpdate
from jobcopilot_profile.services.llm_key_check import validate_llm_key
from jobcopilot_shared.exceptions import ExternalServiceError, ValidationError

_USER = uuid.uuid4()


def _client_returning(status_code: int) -> MagicMock:
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=MagicMock(status_code=status_code))
    return client


@pytest.mark.asyncio
async def test_accepted_key_passes() -> None:
    with patch("httpx.AsyncClient", return_value=_client_returning(200)):
        await validate_llm_key("sk-good")


@pytest.mark.asyncio
async def test_unauthorized_key_rejected() -> None:
    with (
        patch("httpx.AsyncClient", return_value=_client_returning(401)),
        pytest.raises(ValidationError),
    ):
        await validate_llm_key("sk-bad")


@pytest.mark.asyncio
async def test_provider_error_reported_as_external() -> None:
    with (
        patch("httpx.AsyncClient", return_value=_client_returning(500)),
        pytest.raises(ExternalServiceError),
    ):
        await validate_llm_key("sk-any")


@pytest.mark.asyncio
async def test_provider_unreachable_reported_as_external() -> None:
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(side_effect=httpx.ConnectError("down"))
    with patch("httpx.AsyncClient", return_value=client), pytest.raises(ExternalServiceError):
        await validate_llm_key("sk-any")


@pytest.mark.asyncio
async def test_save_rejects_invalid_key_before_persisting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_key_mode", "byo")
    with (
        patch(
            "jobcopilot_profile.routers.profiles.validate_llm_key",
            new_callable=AsyncMock,
            side_effect=ValidationError("rejected"),
        ),
        patch(
            "jobcopilot_profile.repositories.profile_repo.ProfileRepository.update_credentials",
            new_callable=AsyncMock,
        ) as update,
        pytest.raises(ValidationError),
    ):
        await update_credentials(
            CredentialsUpdate(llm_api_key="sk-bad"),
            session=AsyncMock(),
            tenant_id=_USER,
            user_id=_USER,
        )
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_clearing_key_skips_provider_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_key_mode", "byo")
    with (
        patch(
            "jobcopilot_profile.routers.profiles.validate_llm_key",
            new_callable=AsyncMock,
        ) as validate,
        patch(
            "jobcopilot_profile.repositories.profile_repo.ProfileRepository.update_credentials",
            new_callable=AsyncMock,
        ) as update,
    ):
        await update_credentials(
            CredentialsUpdate(llm_api_key=""),
            session=AsyncMock(),
            tenant_id=_USER,
            user_id=_USER,
        )
    validate.assert_not_awaited()
    update.assert_awaited_once()
