"""Drop linkedin_cookie_enc — credential-free discovery (ADR-006).

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_SCHEMA = "profile_schema"


def upgrade() -> None:
    op.drop_column("profiles", "linkedin_cookie_enc", schema=_SCHEMA)


def downgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("linkedin_cookie_enc", sa.Text, nullable=True),
        schema=_SCHEMA,
    )
