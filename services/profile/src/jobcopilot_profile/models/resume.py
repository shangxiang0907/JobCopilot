import uuid
from datetime import datetime
from typing import Any

from jobcopilot_shared.models.base import Base
from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

_SCHEMA = "profile_schema"
_TS = DateTime(timezone=True)


class Resume(Base):
    __tablename__ = "resumes"
    # Names must match migration 0001 / the live DB exactly (alembic check).
    __table_args__ = (
        Index("ix_resumes_user_id", "user_id"),
        Index("ix_resumes_user_default", "user_id", "is_default"),
        {"schema": _SCHEMA},
    )

    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    # Extracted text + basic section structure; embedding lives in Qdrant
    parsed_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # User-supplied label ("backend-focused") and notes — how a user tells
    # several versions apart without reading file names.
    label: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    # "Use this one unless something more specific is chosen." A per-application
    # resume_id always wins over it (PRD v0.3).
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)
