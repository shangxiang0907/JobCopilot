"""init agent_schema

Revision ID: 0001
Revises:
Create Date: 2026-06-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_SCHEMA = "agent_schema"
_NOW = sa.func.now()
_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    op.create_table(
        "job_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("jd_structured", JSONB, nullable=True),
        sa.Column("skills_required", JSONB, nullable=True),
        sa.Column("match_score", sa.Float, nullable=True),
        sa.Column("resume_suggestions", JSONB, nullable=True),
        sa.Column("interview_questions", JSONB, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", _TS, nullable=False, server_default=_NOW),
        sa.Column("updated_at", _TS, nullable=False, server_default=_NOW),
        schema=_SCHEMA,
    )
    op.create_index("ix_job_analyses_job_id", "job_analyses", ["job_id"], schema=_SCHEMA)
    op.create_index("ix_job_analyses_user_id", "job_analyses", ["user_id"], schema=_SCHEMA)
    op.create_index(
        "ix_job_analyses_user_job",
        "job_analyses",
        ["user_id", "job_id"],
        unique=True,
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("job_analyses", schema=_SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA}")
