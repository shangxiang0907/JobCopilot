import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, HttpUrl, model_validator

from jobcopilot_job.schemas.job import NonBlankStr


class CompanyCreate(BaseModel):
    name: NonBlankStr
    industry: str | None = None
    size: str | None = None
    website: HttpUrl | None = None
    notes: str | None = None
    is_blacklisted: bool = False


class CompanyUpdate(BaseModel):
    """Partial update where an omitted field and an explicit `null` differ.

    Omitted = leave unchanged; `null` = clear the value. `exclude_none` would
    make every optional field write-once: the user deletes the industry in the
    edit form, saves, and the old value comes back with nothing logged.
    """

    name: NonBlankStr | None = None
    industry: str | None = None
    size: str | None = None
    website: HttpUrl | None = None
    notes: str | None = None
    is_blacklisted: bool | None = None

    @model_validator(mode="after")
    def _not_nullable_fields(self) -> Self:
        # companies.name and .is_blacklisted are NOT NULL; an explicit null
        # would surface as a database 500 rather than a readable rejection.
        cleared = [
            f
            for f in ("name", "is_blacklisted")
            if f in self.model_fields_set and getattr(self, f) is None
        ]
        if cleared:
            raise ValueError(f"these fields cannot be cleared: {', '.join(cleared)}")
        return self


class CompanyResponse(BaseModel):
    company_id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    industry: str | None
    size: str | None
    website: str | None
    notes: str | None
    is_blacklisted: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
