from datetime import UTC

from fastapi import APIRouter, status
from jobcopilot_shared.crypto import encrypt
from jobcopilot_shared.exceptions import NotFoundError
from jobcopilot_shared.logging import get_logger

from app.deps import SessionDep, TenantIdDep, UserIdDep
from app.repositories.profile_repo import ProfileRepository
from app.schemas.profile import CredentialsUpdate, ProfileResponse, ProfileUpsert

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

        from app.models.profile import Profile

        now = datetime.now(UTC)
        empty = Profile(
            user_id=user_id,
            personal_info=None,
            preferences=None,
            linkedin_cookie_enc=None,
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
    repo = ProfileRepository(session)
    await repo.update_credentials(user_id, body, encrypt)
    logger.info("credentials_updated", user_id=str(user_id))
