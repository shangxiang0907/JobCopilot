"""init discovery_schema

Revision ID: 0001
Revises:
Create Date: 2026-06-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_SCHEMA = "discovery_schema"
_NOW = sa.func.now()
_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    op.create_table(
        "discovery_configs",
        sa.Column("config_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("keywords", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("locations", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("job_types", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("salary_min", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("schedule_cron", sa.String(100), nullable=True),
        sa.Column("last_run_at", _TS, nullable=True),
        sa.Column("created_at", _TS, nullable=False, server_default=_NOW),
        sa.Column("updated_at", _TS, nullable=False, server_default=_NOW),
        schema=_SCHEMA,
    )
    op.create_index("ix_discovery_configs_user_id", "discovery_configs", ["user_id"], schema=_SCHEMA)

    op.create_table(
        "discovery_runs",
        sa.Column("run_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("config_id", UUID(as_uuid=True), nullable=False),
        sa.Column("temporal_run_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("jobs_discovered", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", _TS, nullable=False, server_default=_NOW),
        sa.Column("finished_at", _TS, nullable=True),
        schema=_SCHEMA,
    )
    op.create_index("ix_discovery_runs_user_id", "discovery_runs", ["user_id"], schema=_SCHEMA)
    op.create_index("ix_discovery_runs_config_id", "discovery_runs", ["config_id"], schema=_SCHEMA)


def downgrade() -> None:
    op.drop_table("discovery_runs", schema=_SCHEMA)
    op.drop_table("discovery_configs", schema=_SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA}")
