"""An application records which resume it was submitted with (PRD v0.3).

Three states must stay distinguishable forever:
  resume_id NULL                     -> the user never recorded it
  resume_id set, resolves in Profile -> shown normally
  resume_id set, no longer resolves  -> the resume was deleted; the snapshot
                                        keeps the record readable

Collapsing the third into the first is the failure this test file guards: an
application is a historical fact, and tidying the resume library must not
silently rewrite it.
"""

import uuid

import pytest
from jobcopilot_job.schemas.application import (
    ApplicationCreate,
    ApplicationUpdate,
    ResumeSnapshot,
)
from pydantic import ValidationError


def _snapshot() -> ResumeSnapshot:
    return ResumeSnapshot(file_name="backend-cv.pdf", version=3, label="backend-focused")


def test_binding_omitted_entirely_means_not_recorded() -> None:
    body = ApplicationCreate(job_id=uuid.uuid4())
    assert body.resume_id is None
    assert body.resume_snapshot is None


def test_id_and_snapshot_together_are_accepted() -> None:
    body = ApplicationCreate(
        job_id=uuid.uuid4(),
        resume_id=uuid.uuid4(),
        resume_snapshot=_snapshot(),
    )
    assert body.resume_snapshot is not None
    assert body.resume_snapshot.version == 3


def test_id_without_snapshot_is_rejected() -> None:
    """An id alone becomes unreadable the moment the resume is deleted."""
    with pytest.raises(ValidationError, match="must be provided together"):
        ApplicationCreate(job_id=uuid.uuid4(), resume_id=uuid.uuid4())


def test_snapshot_without_id_is_rejected() -> None:
    """A snapshot alone points at nothing."""
    with pytest.raises(ValidationError, match="must be provided together"):
        ApplicationCreate(job_id=uuid.uuid4(), resume_snapshot=_snapshot())


def test_update_enforces_the_same_invariant() -> None:
    with pytest.raises(ValidationError, match="must be provided together"):
        ApplicationUpdate(resume_id=uuid.uuid4())


def test_notes_only_update_leaves_the_binding_alone() -> None:
    body = ApplicationUpdate(notes="phone screen booked")
    assert body.resume_id is None
    assert body.resume_snapshot is None


def test_snapshot_label_is_optional() -> None:
    """A user who never labelled the resume still gets file name and version."""
    snapshot = ResumeSnapshot(file_name="cv.pdf", version=1)
    assert snapshot.label is None


def test_snapshot_rejects_a_version_below_one() -> None:
    """Versions start at 1; 0 would signal a caller inventing values."""
    with pytest.raises(ValidationError):
        ResumeSnapshot(file_name="cv.pdf", version=0)
