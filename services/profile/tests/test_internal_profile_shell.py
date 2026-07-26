"""Regression: a user without a profile row must still resolve their resume.

The profile row is optional side data (personal info / BYO key) and is
unreachable under LLM_KEY_MODE=platform, where saving credentials is rejected
server-side. GET /internal/profiles/{user_id} used to 404 in that case, and its
three callers all read that as "this user has no resume": matching told users
with an active resume to upload one, and the analyzer scored jobs against an
empty resume without surfacing anything.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from jobcopilot_profile.models.resume import Resume
from jobcopilot_profile.routers.internal import internal_get_profile

_USER = uuid.uuid4()


def _resume(raw_text: str) -> Resume:
    return Resume(
        resume_id=uuid.uuid4(),
        user_id=_USER,
        file_name="cv.pdf",
        file_url="/data/resumes/cv.pdf",
        parsed_data={"raw_text": raw_text},
        version=1,
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_missing_profile_row_still_returns_active_resume() -> None:
    with (
        patch(
            "jobcopilot_profile.repositories.profile_repo.ProfileRepository.get_by_user_or_none",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "jobcopilot_profile.repositories.resume_repo.ResumeRepository.get_active",
            new_callable=AsyncMock,
            return_value=_resume("Senior Python engineer, 8 years"),
        ),
    ):
        response = await internal_get_profile(_USER, session=AsyncMock())

    assert response.profile_id is None
    assert response.user_id == _USER
    assert response.personal_info is None
    assert response.llm_api_key is None
    assert response.active_resume is not None
    assert response.active_resume_text == "Senior Python engineer, 8 years"


@pytest.mark.asyncio
async def test_missing_profile_and_no_resume_reports_empty_not_error() -> None:
    with (
        patch(
            "jobcopilot_profile.repositories.profile_repo.ProfileRepository.get_by_user_or_none",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "jobcopilot_profile.repositories.resume_repo.ResumeRepository.get_active",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        response = await internal_get_profile(_USER, session=AsyncMock())

    assert response.active_resume is None
    assert response.active_resume_text == ""
