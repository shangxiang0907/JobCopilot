"""Record which resume an application was submitted with (PRD v0.3).

resume_id is a PLAIN UUID with no foreign key on purpose: applications live in
job_schema, resumes in profile_schema, and cross-schema FKs/JOINs are forbidden
(CLAUDE.md). The Job Service stores it opaquely and never dereferences it.

NULL means "not recorded" and NEVER "the user's default resume" — collapsing
those two would make an unanswered question indistinguishable from an answer.

resume_snapshot holds the resume's display identity at the moment it was
attached ({file_name, version, label}). Without it, deleting a resume would turn
its applications back into "not recorded"; with it they still read
"v3 - backend-focused (deleted)". An application is a historical fact, so
cleaning up the resume library must not rewrite what actually happened.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_SCHEMA = "job_schema"


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("resume_id", UUID(as_uuid=True), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "applications",
        sa.Column("resume_snapshot", JSONB, nullable=True),
        schema=_SCHEMA,
    )
    # Supports "how many applications reference this resume?", which the delete
    # confirmation dialog asks before a user removes a resume.
    op.create_index(
        "ix_applications_resume_id",
        "applications",
        ["resume_id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_applications_resume_id", table_name="applications", schema=_SCHEMA)
    op.drop_column("applications", "resume_snapshot", schema=_SCHEMA)
    op.drop_column("applications", "resume_id", schema=_SCHEMA)
