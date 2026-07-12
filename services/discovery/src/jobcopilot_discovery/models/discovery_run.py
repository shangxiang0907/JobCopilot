import uuid
from datetime import datetime

from jobcopilot_shared.models.base import Base
from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

_SCHEMA = "discovery_schema"
_TS = DateTime(timezone=True)


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"
    # Names must match migration 0001 / the live DB exactly (alembic check).
    __table_args__ = (
        Index("ix_discovery_runs_user_id", "user_id"),
        Index("ix_discovery_runs_config_id", "config_id"),
        {"schema": _SCHEMA},
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    config_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Temporal-assigned workflow run identifier
    temporal_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # pending | running | completed | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    jobs_discovered: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(_TS, nullable=True)
