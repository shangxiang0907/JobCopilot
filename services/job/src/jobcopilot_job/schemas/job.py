import uuid
from datetime import datetime
from typing import Annotated, Any, Self

from pydantic import BaseModel, HttpUrl, StringConstraints, field_validator, model_validator

JOB_TYPES = frozenset({"full_time", "part_time", "contract", "internship", "remote"})

# NOT NULL columns in job_schema.jobs. Under the explicit-null PATCH semantics
# below, sending `null` for one of these would surface as a database 500 rather
# than a readable rejection.
_JOB_REQUIRED = ("title", "company_name", "url")

NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _check_job_type(v: str | None) -> str | None:
    if v is not None and v not in JOB_TYPES:
        raise ValueError(f"job_type must be one of {sorted(JOB_TYPES)}")
    return v


class JobCreate(BaseModel):
    title: NonBlankStr
    company_name: NonBlankStr
    url: HttpUrl
    source: str = "manual"
    company_id: uuid.UUID | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    location: str | None = None
    job_type: str | None = None
    raw_jd: str | None = None

    _validate_job_type = field_validator("job_type")(_check_job_type)


class JobUpdate(BaseModel):
    """Partial update where an omitted field and an explicit `null` differ.

    Omitted = leave unchanged; `null` = clear the value. Collapsing the two (as
    `exclude_none` did) makes optional fields unclearable: the user empties the
    salary in the edit form, saves, and watches the old number come back, with
    nothing in any log to explain it. `company_id: null` is how the user
    unlinks a job from its company (PRD §3.4).
    """

    title: NonBlankStr | None = None
    company_name: NonBlankStr | None = None
    url: HttpUrl | None = None
    raw_jd: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    location: str | None = None
    job_type: str | None = None
    company_id: uuid.UUID | None = None

    _validate_job_type = field_validator("job_type")(_check_job_type)

    @model_validator(mode="after")
    def _required_fields_cannot_be_cleared(self) -> Self:
        cleared = [
            f for f in _JOB_REQUIRED if f in self.model_fields_set and getattr(self, f) is None
        ]
        if cleared:
            raise ValueError(f"these fields cannot be cleared: {', '.join(cleared)}")
        return self


class JobResponse(BaseModel):
    job_id: uuid.UUID
    tenant_id: uuid.UUID
    company_id: uuid.UUID | None
    title: str
    company_name: str
    url: str
    source: str
    raw_jd: str | None
    analysis: dict[str, Any] | None
    salary_min: int | None
    salary_max: int | None
    location: str | None
    job_type: str | None
    discovered_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InternalJobCreate(BaseModel):
    """Used by Agent Service to persist a fully-analyzed job."""

    tenant_id: uuid.UUID
    title: str
    company_name: str
    url: str
    source: str = "discovery"
    company_id: uuid.UUID | None = None
    raw_jd: str | None = None
    analysis: dict[str, Any] | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    location: str | None = None
    job_type: str | None = None
    discovered_at: datetime | None = None


class InternalJobUpdate(BaseModel):
    """Used by Agent Service to update analysis on an existing job."""

    analysis: dict[str, Any] | None = None
