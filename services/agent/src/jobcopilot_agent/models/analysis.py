import uuid

from jobcopilot_shared.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

_SCHEMA = "agent_schema"


class JobAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "job_analyses"
    __table_args__ = {"schema": _SCHEMA}

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # From AnalyzerGraph
    jd_structured: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    skills_required: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # From ResumeGraph
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    resume_suggestions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # From InterviewGraph
    interview_questions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
