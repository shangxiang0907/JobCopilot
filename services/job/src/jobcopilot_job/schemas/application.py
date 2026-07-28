import uuid
from datetime import datetime
from typing import Any, Literal, Self, get_args

from pydantic import BaseModel, Field, model_validator

# Single source of truth for application statuses — a Literal so the OpenAPI
# schema carries the enum and the generated frontend types get the union.
ApplicationStatusName = Literal[
    "discovered", "applied", "interviewing", "offer", "rejected", "withdrawn"
]
VALID_STATUSES = frozenset(get_args(ApplicationStatusName))


class ResumeSnapshot(BaseModel):
    """How the attached resume identified itself when it was attached.

    The Job Service cannot look this up: resumes live in profile_schema and
    cross-schema JOINs are forbidden, so the caller supplies it. Typed rather
    than free-form JSON so the stored shape stays predictable for the UI.
    """

    file_name: str = Field(max_length=255)
    version: int = Field(ge=1)
    label: str | None = Field(default=None, max_length=100)


class _ResumeBinding(BaseModel):
    """resume_id and its snapshot travel together, or not at all.

    Enforced rather than documented, because half a binding reintroduces exactly
    the ambiguity the snapshot exists to remove: an id with no snapshot becomes
    unreadable the moment the resume is deleted, and a snapshot with no id
    points at nothing.
    """

    resume_id: uuid.UUID | None = None
    resume_snapshot: ResumeSnapshot | None = None

    @model_validator(mode="after")
    def _binding_is_all_or_nothing(self) -> Self:
        if (self.resume_id is None) != (self.resume_snapshot is None):
            raise ValueError("resume_id and resume_snapshot must be provided together")
        return self


class ApplicationCreate(_ResumeBinding):
    job_id: uuid.UUID
    notes: str | None = None


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatusName
    note: str | None = None


class ApplicationUpdate(_ResumeBinding):
    notes: str | None = None


class ApplicationJobSummary(BaseModel):
    """Job fields a list view needs alongside an application (kanban cards etc.)."""

    job_id: uuid.UUID
    title: str
    company_name: str
    location: str | None
    job_type: str | None
    url: str

    model_config = {"from_attributes": True}


class ApplicationResponse(BaseModel):
    application_id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    status: ApplicationStatusName
    # NULL = the user never recorded which resume they used. A value that no
    # longer resolves in Profile Service means the resume was deleted — the
    # snapshot below keeps that case readable.
    resume_id: uuid.UUID | None
    resume_snapshot: ResumeSnapshot | None
    match_score: float | None
    resume_suggestions: dict[str, Any] | None
    notes: str | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Populated by the list endpoint (joined in one query); None elsewhere.
    job: ApplicationJobSummary | None = None

    model_config = {"from_attributes": True}


class ApplicationEventResponse(BaseModel):
    event_id: uuid.UUID
    application_id: uuid.UUID
    from_status: str
    to_status: str
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InternalAnalysisUpdate(BaseModel):
    """Used by Agent Service to push match analysis results."""

    match_score: float | None = None
    resume_suggestions: dict[str, Any] | None = None


class InternalKanbanUpdate(BaseModel):
    """Used by the Agent Service update_kanban tool to move an application by job id."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    status: ApplicationStatusName
    note: str | None = None
