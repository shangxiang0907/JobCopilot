import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Discovery Config ──────────────────────────────────────────────────────────

class DiscoveryConfigCreate(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    job_types: list[str] = Field(default_factory=list)
    salary_min: int | None = None
    is_active: bool = True
    schedule_cron: str | None = None


class DiscoveryConfigUpdate(BaseModel):
    keywords: list[str] | None = None
    locations: list[str] | None = None
    job_types: list[str] | None = None
    salary_min: int | None = None
    is_active: bool | None = None
    schedule_cron: str | None = None


class DiscoveryConfigResponse(BaseModel):
    model_config = {"from_attributes": True}

    config_id: uuid.UUID
    user_id: uuid.UUID
    keywords: list[str]
    locations: list[str]
    job_types: list[str]
    salary_min: int | None
    is_active: bool
    schedule_cron: str | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ── Discovery Run ─────────────────────────────────────────────────────────────

class TriggerRunRequest(BaseModel):
    config_id: uuid.UUID


class DiscoveryRunResponse(BaseModel):
    model_config = {"from_attributes": True}

    run_id: uuid.UUID
    user_id: uuid.UUID
    config_id: uuid.UUID
    temporal_run_id: str | None
    status: str
    jobs_discovered: int
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
