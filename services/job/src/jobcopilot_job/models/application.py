import uuid
from datetime import datetime
from typing import Any

from jobcopilot_shared.models.base import Base
from sqlalchemy import DateTime, Float, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

_SCHEMA = "job_schema"
_TS = DateTime(timezone=True)

# Valid status values — also enforced by VALID_TRANSITIONS in application_repo
APPLICATION_STATUSES = ("discovered", "applied", "interviewing", "offer", "rejected", "withdrawn")

VALID_TRANSITIONS: dict[str, set[str]] = {
    "discovered": {"applied", "withdrawn"},
    "applied": {"interviewing", "rejected", "withdrawn"},
    "interviewing": {"offer", "rejected", "withdrawn"},
    "offer": set(),
    "rejected": set(),
    "withdrawn": set(),
}


class Application(Base):
    __tablename__ = "applications"
    # Names must match migration 0001 / the live DB exactly (alembic check).
    __table_args__ = (
        Index("ix_applications_user_id", "user_id"),
        Index("ix_applications_job_id", "job_id"),
        Index("ix_applications_user_job", "user_id", "job_id", unique=True),
        {"schema": _SCHEMA},
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="discovered")
    match_score: Mapped[float | None] = mapped_column(Float)
    resume_suggestions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(_TS)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        _TS, server_default=func.now(), onupdate=func.now(), nullable=False
    )
