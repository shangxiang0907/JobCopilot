"""Default-resume and label/notes semantics introduced by PRD v0.3.

`is_active` was renamed to `is_default` because the flag never meant "switched
on" — it means "use this one when nothing more specific is chosen". An
application's own resume_id always wins over it, so changing the default must
never rewrite history, and deleting the default must never silently promote a
replacement.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jobcopilot_profile.models.resume import Resume
from jobcopilot_profile.repositories.resume_repo import ResumeRepository

_USER = uuid.uuid4()


def _resume(**kwargs: object) -> Resume:
    defaults: dict[str, object] = {
        "resume_id": uuid.uuid4(),
        "user_id": _USER,
        "file_name": "cv.pdf",
        "file_url": "/data/resumes/cv.pdf",
        "version": 1,
        "is_default": False,
    }
    defaults.update(kwargs)
    return Resume(**defaults)


def _repo() -> tuple[ResumeRepository, AsyncMock]:
    session = AsyncMock()
    session.add = MagicMock()  # Session.add is sync — AsyncMock would leave a coroutine unawaited
    return ResumeRepository(session), session


@pytest.mark.asyncio
async def test_set_default_clears_the_flag_across_the_users_resumes() -> None:
    """At most one default per user, enforced by clearing before setting."""
    repo, session = _repo()
    target = _resume()
    with patch.object(ResumeRepository, "get", new_callable=AsyncMock, return_value=target):
        result = await repo.set_default(_USER, target.resume_id)

    assert result.is_default is True
    # The bulk UPDATE clearing every other resume must run before the set.
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_label_and_notes_update_independently() -> None:
    """None means "leave unchanged", so a partial edit cannot blank the other."""
    repo, _ = _repo()
    existing = _resume(label="backend-focused", notes="sent to Acme")
    with patch.object(ResumeRepository, "get", new_callable=AsyncMock, return_value=existing):
        result = await repo.update_metadata(_USER, existing.resume_id, label="frontend", notes=None)

    assert result.label == "frontend"
    assert result.notes == "sent to Acme"


@pytest.mark.asyncio
async def test_empty_string_clears_a_field() -> None:
    """Clearing is explicit — "" stores NULL, distinct from omitting the field."""
    repo, _ = _repo()
    existing = _resume(label="backend-focused", notes="sent to Acme")
    with patch.object(ResumeRepository, "get", new_callable=AsyncMock, return_value=existing):
        result = await repo.update_metadata(_USER, existing.resume_id, label="", notes=None)

    assert result.label is None
    assert result.notes == "sent to Acme"


@pytest.mark.asyncio
async def test_first_upload_takes_the_default_slot() -> None:
    repo, _ = _repo()
    with (
        patch.object(ResumeRepository, "get_default", new_callable=AsyncMock, return_value=None),
        patch.object(ResumeRepository, "_next_version", new_callable=AsyncMock, return_value=1),
    ):
        resume = await repo.create(_USER, "cv.pdf", "/data/resumes/cv.pdf", {"raw_text": "x"})

    assert resume.is_default is True


@pytest.mark.asyncio
async def test_later_upload_never_steals_the_default() -> None:
    repo, _ = _repo()
    with (
        patch.object(
            ResumeRepository, "get_default", new_callable=AsyncMock, return_value=_resume()
        ),
        patch.object(ResumeRepository, "_next_version", new_callable=AsyncMock, return_value=2),
    ):
        resume = await repo.create(_USER, "cv2.pdf", "/data/resumes/cv2.pdf", {"raw_text": "x"})

    assert resume.is_default is False
