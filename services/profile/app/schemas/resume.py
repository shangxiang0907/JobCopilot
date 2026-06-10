import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ResumeResponse(BaseModel):
    resume_id: uuid.UUID
    user_id: uuid.UUID
    file_name: str
    file_url: str
    parsed_data: dict[str, Any] | None
    version: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeActivate(BaseModel):
    is_active: bool
