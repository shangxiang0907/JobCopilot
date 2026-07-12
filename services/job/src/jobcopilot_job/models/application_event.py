import uuid
from datetime import datetime

from jobcopilot_shared.models.base import Base
from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

_SCHEMA = "job_schema"
_TS = DateTime(timezone=True)


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    # Names must match migration 0001 / the live DB exactly (alembic check).
    __table_args__ = (
        Index("ix_application_events_application_id", "application_id"),
        {"schema": _SCHEMA},
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    from_status: Mapped[str] = mapped_column(String(20), nullable=False)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)
