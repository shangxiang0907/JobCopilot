"""Rename resumes.is_active -> is_default and add label/notes (PRD v0.3).

The flag never meant "this resume is switched on" — it meant "use this one when
nothing more specific is chosen". PRD v0.3 makes that explicit because
applications now record their own resume_id, and a per-application choice wins
over the default. Renaming the column keeps the schema honest about which of the
two is authoritative.

label/notes let a user tell several versions apart ("backend-focused",
"after the 2026 promotion") instead of reading file names and version numbers.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_SCHEMA = "profile_schema"


def upgrade() -> None:
    op.alter_column("resumes", "is_active", new_column_name="is_default", schema=_SCHEMA)
    # The index name has to track the column name — alembic check compares both.
    op.drop_index("ix_resumes_user_active", table_name="resumes", schema=_SCHEMA)
    op.create_index(
        "ix_resumes_user_default",
        "resumes",
        ["user_id", "is_default"],
        schema=_SCHEMA,
    )
    op.add_column("resumes", sa.Column("label", sa.String(100), nullable=True), schema=_SCHEMA)
    op.add_column("resumes", sa.Column("notes", sa.Text, nullable=True), schema=_SCHEMA)


def downgrade() -> None:
    op.drop_column("resumes", "notes", schema=_SCHEMA)
    op.drop_column("resumes", "label", schema=_SCHEMA)
    op.drop_index("ix_resumes_user_default", table_name="resumes", schema=_SCHEMA)
    op.alter_column("resumes", "is_default", new_column_name="is_active", schema=_SCHEMA)
    op.create_index(
        "ix_resumes_user_active",
        "resumes",
        ["user_id", "is_active"],
        schema=_SCHEMA,
    )
