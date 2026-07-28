import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ResumeResponse(BaseModel):
    resume_id: uuid.UUID
    user_id: uuid.UUID
    file_name: str
    file_url: str
    parsed_data: dict[str, Any] | None
    version: int
    label: str | None
    notes: str | None
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeSetDefault(BaseModel):
    is_default: bool


class ResumeUpdate(BaseModel):
    """Label/notes edit. Both fields are optional and independently clearable.

    `None` means "leave unchanged" — clearing a field is an explicit empty
    string, so a partial update can never blank out the other field by omission.
    """

    label: str | None = Field(default=None, max_length=100)
    notes: str | None = None
