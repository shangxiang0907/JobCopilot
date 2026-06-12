import uuid
from datetime import datetime
from typing import Any

from jobcopilot_shared.models.base import Base
from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

_SCHEMA = "profile_schema"
_TS = DateTime(timezone=True)


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = {"schema": _SCHEMA}

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, index=True
    )
    personal_info: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    preferences: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # AES-256-GCM encrypted; never returned in external API responses
    linkedin_cookie_enc: Mapped[str | None] = mapped_column(Text)
    llm_api_key_enc: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        _TS, server_default=func.now(), onupdate=func.now(), nullable=False
    )
