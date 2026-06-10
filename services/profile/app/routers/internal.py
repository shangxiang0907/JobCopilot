"""Internal routes — K8s DNS only. Kong blocks external access."""

import uuid

from fastapi import APIRouter
from jobcopilot_shared.crypto import decrypt
from jobcopilot_shared.exceptions import NotFoundError
from jobcopilot_shared.logging import get_logger

from app.deps import SessionDep
from app.repositories.profile_repo import ProfileRepository
from app.repositories.resume_repo import ResumeRepository
from app.schemas.profile import InternalProfileResponse
from app.schemas.resume import ResumeResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/profiles/{user_id}", response_model=InternalProfileResponse)
async def internal_get_profile(
    user_id: uuid.UUID,
    session: SessionDep,
) -> InternalProfileResponse:
    """Full profile including decrypted credentials — for Agent & Discovery Services."""
    profile_repo = ProfileRepository(session)
    resume_repo = ResumeRepository(session)

    try:
        profile = await profile_repo.get_by_user(user_id)
    except NotFoundError:
        raise

    active_resume = await resume_repo.get_active(user_id)
    active_resume_data = (
        ResumeResponse.model_validate(active_resume).model_dump() if active_resume else None
    )

    return InternalProfileResponse(
        profile_id=profile.profile_id,
        user_id=profile.user_id,
        personal_info=profile.personal_info,
        preferences=profile.preferences,
        linkedin_cookie=_safe_decrypt(profile.linkedin_cookie_enc),
        llm_api_key=_safe_decrypt(profile.llm_api_key_enc),
        active_resume=active_resume_data,
    )


@router.get("/profiles/{user_id}/cookie")
async def internal_get_cookie(
    user_id: uuid.UUID,
    session: SessionDep,
) -> dict[str, str | None]:
    """Minimal endpoint for Discovery Service to fetch the LinkedIn cookie only."""
    profile_repo = ProfileRepository(session)
    profile = await profile_repo.get_by_user(user_id)
    return {"linkedin_cookie": _safe_decrypt(profile.linkedin_cookie_enc)}


def _safe_decrypt(encrypted: str | None) -> str | None:
    if not encrypted:
        return None
    try:
        return decrypt(encrypted)
    except Exception as exc:
        logger.error("decrypt_failed", error=str(exc))
        return None
