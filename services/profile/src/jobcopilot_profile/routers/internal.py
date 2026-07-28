"""Internal routes — K8s DNS only. Kong blocks external access."""

import uuid

from fastapi import APIRouter
from jobcopilot_shared.crypto import decrypt
from jobcopilot_shared.logging import get_logger

from jobcopilot_profile.config import settings
from jobcopilot_profile.deps import SessionDep
from jobcopilot_profile.repositories.profile_repo import ProfileRepository
from jobcopilot_profile.repositories.resume_repo import ResumeRepository
from jobcopilot_profile.schemas.profile import InternalProfileResponse
from jobcopilot_profile.schemas.resume import ResumeResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/profiles/{user_id}", response_model=InternalProfileResponse)
async def internal_get_profile(
    user_id: uuid.UUID,
    session: SessionDep,
) -> InternalProfileResponse:
    """Full profile including decrypted credentials — for Agent & Discovery Services.

    A missing profile row is NOT a 404. The row only exists once a user saves
    personal info or a BYO key, and under LLM_KEY_MODE=platform neither path is
    reachable (credentials are rejected server-side), so hosted deployments have
    no rows at all. 404-ing here made callers believe the user had no resume:
    matching reported "no active resume" to users who had one, and the analyzer
    silently scored jobs against an empty resume. The row is optional side data;
    the resume is the payload. Mirrors GET /v1/profiles/me, which has always
    returned an empty shell rather than 404.
    """
    profile_repo = ProfileRepository(session)
    resume_repo = ResumeRepository(session)

    profile = await profile_repo.get_by_user_or_none(user_id)

    default_resume = await resume_repo.get_default(user_id)
    default_resume_data = (
        ResumeResponse.model_validate(default_resume).model_dump() if default_resume else None
    )
    default_resume_text = ""
    if default_resume is not None and default_resume.parsed_data:
        default_resume_text = str(default_resume.parsed_data.get("raw_text") or "")

    return InternalProfileResponse(
        profile_id=profile.profile_id if profile else None,
        user_id=user_id,
        personal_info=profile.personal_info if profile else None,
        preferences=profile.preferences if profile else None,
        llm_api_key=_safe_decrypt(profile.llm_api_key_enc) if profile else None,
        default_resume=default_resume_data,
        default_resume_text=default_resume_text,
    )


def _safe_decrypt(encrypted: str | None) -> str | None:
    if not encrypted:
        return None
    try:
        return decrypt(encrypted, settings.encryption_key)
    except Exception as exc:
        logger.error("decrypt_failed", error=str(exc))
        return None
