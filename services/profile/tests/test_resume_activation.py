"""A user's first resume must be active on upload.

Every AI action fail-fasts on no_active_resume, and uploads were created with
is_active=False, so a new user who had just uploaded a resume still could not
use any AI feature until they found the Activate button.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jobcopilot_profile.models.resume import Resume
from jobcopilot_profile.repositories.resume_repo import ResumeRepository

_USER = uuid.uuid4()


async def _create(existing_active: Resume | None) -> Resume:
    session = AsyncMock()
    session.add = MagicMock()  # Session.add is sync — AsyncMock would leave a coroutine unawaited
    repo = ResumeRepository(session)
    with (
        patch.object(
            ResumeRepository, "get_active", new_callable=AsyncMock, return_value=existing_active
        ),
        patch.object(ResumeRepository, "_next_version", new_callable=AsyncMock, return_value=1),
    ):
        return await repo.create(_USER, "cv.pdf", "/data/resumes/cv.pdf", {"raw_text": "text"})


@pytest.mark.asyncio
async def test_first_resume_is_activated_on_upload() -> None:
    resume = await _create(existing_active=None)
    assert resume.is_active is True


@pytest.mark.asyncio
async def test_later_upload_does_not_steal_active_flag() -> None:
    """An explicit choice of active resume survives subsequent uploads."""
    resume = await _create(existing_active=Resume(resume_id=uuid.uuid4(), user_id=_USER))
    assert resume.is_active is False
