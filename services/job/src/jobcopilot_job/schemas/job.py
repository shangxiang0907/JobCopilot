import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, HttpUrl, field_validator


class JobCreate(BaseModel):
    title: str
    company_name: str
    url: HttpUrl
    source: str = "manual"
    company_id: uuid.UUID | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    location: str | None = None
    job_type: str | None = None
    raw_jd: str | None = None

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str | None) -> str | None:
        allowed = {"full_time", "part_time", "contract", "internship", "remote"}
        if v is not None and v not in allowed:
            raise ValueError(f"job_type must be one of {allowed}")
        return v


class JobUpdate(BaseModel):
    title: str | None = None
    company_name: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    location: str | None = None
    job_type: str | None = None
    company_id: uuid.UUID | None = None


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
