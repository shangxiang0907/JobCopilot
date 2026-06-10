"""init job_schema

Revision ID: 0001
Revises:
Create Date: 2026-06-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_SCHEMA = "job_schema"
_NOW = sa.func.now()
_TS = sa.DateTime(timezone=True)


def _ts(nullable: bool = False, default: bool = True) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(_TS, nullable=nullable, server_default=_NOW if default else None)


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    op.create_table(
        "companies",
        sa.Column("company_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("size", sa.String(50), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_blacklisted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", _TS, nullable=False, server_default=_NOW),
        sa.Column("updated_at", _TS, nullable=False, server_default=_NOW),
        schema=_SCHEMA,
    )
    op.create_index("ix_companies_tenant_id", "companies", ["tenant_id"], schema=_SCHEMA)

    op.create_table(
        "jobs",
        sa.Column("job_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("url", sa.Text, nullable=False, unique=True),
        sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("raw_jd", sa.Text, nullable=True),
        sa.Column("analysis", JSONB, nullable=True),
        sa.Column("salary_min", sa.Integer, nullable=True),
        sa.Column("salary_max", sa.Integer, nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("job_type", sa.String(50), nullable=True),
        sa.Column("discovered_at", _TS, nullable=True),
        sa.Column("created_at", _TS, nullable=False, server_default=_NOW),
        sa.Column("updated_at", _TS, nullable=False, server_default=_NOW),
        schema=_SCHEMA,
    )
    op.create_index("ix_jobs_tenant_id", "jobs", ["tenant_id"], schema=_SCHEMA)

    op.create_table(
        "applications",
        sa.Column("application_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="discovered"),
        sa.Column("match_score", sa.Float, nullable=True),
        sa.Column("resume_suggestions", JSONB, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("applied_at", _TS, nullable=True),
        sa.Column("created_at", _TS, nullable=False, server_default=_NOW),
        sa.Column("updated_at", _TS, nullable=False, server_default=_NOW),
        schema=_SCHEMA,
    )
    op.create_index("ix_applications_user_id", "applications", ["user_id"], schema=_SCHEMA)
    op.create_index("ix_applications_job_id", "applications", ["job_id"], schema=_SCHEMA)
    op.create_index(
        "ix_applications_user_job",
        "applications",
        ["user_id", "job_id"],
        unique=True,
        schema=_SCHEMA,
    )

    op.create_table(
        "application_events",
        sa.Column("event_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=False),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", _TS, nullable=False, server_default=_NOW),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_application_events_application_id",
        "application_events",
        ["application_id"],
        schema=_SCHEMA,
    )

    op.create_table(
        "user_company_watchlist",
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", _TS, nullable=False, server_default=_NOW),
        sa.PrimaryKeyConstraint("user_id", "company_id", name="pk_user_company_watchlist"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("user_company_watchlist", schema=_SCHEMA)
    op.drop_table("application_events", schema=_SCHEMA)
    op.drop_table("applications", schema=_SCHEMA)
    op.drop_table("jobs", schema=_SCHEMA)
    op.drop_table("companies", schema=_SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA}")
