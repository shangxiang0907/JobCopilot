import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str
    channel: str
    status: str
    metadata_: dict[str, Any]
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationOut]
    total: int
    page: int
    page_size: int


class PreferenceOut(BaseModel):
    id: uuid.UUID
    in_app_enabled: bool
    email_enabled: bool
    email_address: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PreferenceUpdate(BaseModel):
    in_app_enabled: bool | None = None
    email_enabled: bool | None = None
    email_address: str | None = None

    @field_validator("email_address", mode="before")
    @classmethod
    def _validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        # Basic email validation without EmailStr dependency issue
        if "@" not in v:
            raise ValueError("Invalid email address")
        return v


class InternalNotifyRequest(BaseModel):
    """Payload for POST /internal/notify — service-to-service."""

    tenant_id: uuid.UUID
    user_id: uuid.UUID
    type: str
    title: str
    body: str
    channels: list[str] = ["in_app"]
    metadata: dict[str, Any] = {}
