import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl


class CompanyCreate(BaseModel):
    name: str
    industry: str | None = None
    size: str | None = None
    website: HttpUrl | None = None
    notes: str | None = None
    is_blacklisted: bool = False


class CompanyUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    size: str | None = None
    website: HttpUrl | None = None
    notes: str | None = None
    is_blacklisted: bool | None = None


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
