import uuid
from datetime import datetime

from jobcopilot_shared.models.base import Base
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

_SCHEMA = "job_schema"
_TS = DateTime(timezone=True)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = {"schema": _SCHEMA}

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    raw_jd: Mapped[str | None] = mapped_column(Text)
    # Structured analysis produced by AnalyzerGraph (Agent Service writes via internal API)
    analysis: Mapped[dict | None] = mapped_column(JSONB)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(255))
    job_type: Mapped[str | None] = mapped_column(String(50))
    discovered_at: Mapped[datetime | None] = mapped_column(_TS)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        _TS, server_default=func.now(), onupdate=func.now(), nullable=False
    )
