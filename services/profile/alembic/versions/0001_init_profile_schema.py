"""init profile_schema

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

_SCHEMA = "profile_schema"
_NOW = sa.func.now()
_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    op.create_table(
        "profiles",
        sa.Column("profile_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("personal_info", JSONB, nullable=True),
        sa.Column("preferences", JSONB, nullable=True),
        sa.Column("linkedin_cookie_enc", sa.Text, nullable=True),
        sa.Column("llm_api_key_enc", sa.Text, nullable=True),
        sa.Column("created_at", _TS, nullable=False, server_default=_NOW),
        sa.Column("updated_at", _TS, nullable=False, server_default=_NOW),
        schema=_SCHEMA,
    )
    op.create_index("ix_profiles_user_id", "profiles", ["user_id"], schema=_SCHEMA)

    op.create_table(
        "resumes",
        sa.Column("resume_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_url", sa.String(1000), nullable=False),
        sa.Column("parsed_data", JSONB, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", _TS, nullable=False, server_default=_NOW),
        schema=_SCHEMA,
    )
    op.create_index("ix_resumes_user_id", "resumes", ["user_id"], schema=_SCHEMA)
    op.create_index(
        "ix_resumes_user_active",
        "resumes",
        ["user_id", "is_active"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("resumes", schema=_SCHEMA)
    op.drop_table("profiles", schema=_SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA}")
