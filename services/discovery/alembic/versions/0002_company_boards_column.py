"""Add company_boards to discovery_configs (ADR-006 Greenhouse/Lever boards).

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_SCHEMA = "discovery_schema"


def upgrade() -> None:
    op.add_column(
        "discovery_configs",
        sa.Column(
            "company_boards",
            ARRAY(sa.Text),
            nullable=False,
            server_default="{}",
        ),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("discovery_configs", "company_boards", schema=_SCHEMA)
