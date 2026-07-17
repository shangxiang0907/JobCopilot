from datetime import UTC

from fastapi import APIRouter, status
from jobcopilot_shared.crypto import encrypt
from jobcopilot_shared.exceptions import NotFoundError, PermissionDeniedError
from jobcopilot_shared.logging import get_logger

from jobcopilot_profile.config import settings
from jobcopilot_profile.deps import SessionDep, TenantIdDep, UserIdDep
from jobcopilot_profile.repositories.profile_repo import ProfileRepository
from jobcopilot_profile.schemas.profile import CredentialsUpdate, ProfileResponse, ProfileUpsert
from jobcopilot_profile.services.llm_key_check import validate_llm_key

logger = get_logger(__name__)
router = APIRouter(prefix="/v1/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> ProfileResponse:
    repo = ProfileRepository(session)
    try:
        profile = await repo.get_by_user(user_id)
    except NotFoundError:
        # Return an empty profile shell rather than 404 for better UX
        from datetime import datetime

        from jobcopilot_profile.models.profile import Profile

        now = datetime.now(UTC)
        empty = Profile(
            user_id=user_id,
            personal_info=None,
            preferences=None,
            llm_api_key_enc=None,
            created_at=now,
            updated_at=now,
        )
        import uuid

        empty.profile_id = uuid.uuid4()
        return ProfileResponse.from_orm_model(empty)
    return ProfileResponse.from_orm_model(profile)


@router.put("/me", response_model=ProfileResponse)
async def upsert_my_profile(
    body: ProfileUpsert,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> ProfileResponse:
    repo = ProfileRepository(session)
    profile = await repo.upsert(user_id, body)
    return ProfileResponse.from_orm_model(profile)


@router.patch("/me/credentials", status_code=status.HTTP_204_NO_CONTENT)
async def update_credentials(
    body: CredentialsUpdate,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> None:
    # Hosted site (ADR-007): the platform key serves everyone; BYO keys are
    # rejected server-side, not just hidden in the UI.
    if settings.llm_key_mode == "platform":
        raise PermissionDeniedError(
            "API key configuration is disabled on this deployment; the platform provides LLM access"
        )
    # Fail a bad key at save time, not on the first AI action. Clearing the key
    # (empty string) needs no provider round-trip.
    if body.llm_api_key:
        await validate_llm_key(body.llm_api_key)
    repo = ProfileRepository(session)
    await repo.update_credentials(
        user_id, body, lambda value: encrypt(value, settings.encryption_key)
    )
    logger.info("credentials_updated", user_id=str(user_id))
