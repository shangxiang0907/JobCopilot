import uuid
from datetime import datetime
from typing import Any, Literal, get_args

from pydantic import BaseModel

# Single source of truth for application statuses — a Literal so the OpenAPI
# schema carries the enum and the generated frontend types get the union.
ApplicationStatusName = Literal[
    "discovered", "applied", "interviewing", "offer", "rejected", "withdrawn"
]
VALID_STATUSES = frozenset(get_args(ApplicationStatusName))


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID
    notes: str | None = None


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatusName
    note: str | None = None


class ApplicationUpdate(BaseModel):
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
