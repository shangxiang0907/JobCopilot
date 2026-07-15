"""drop IM webhook columns (WeChat/DingTalk channels removed, PRD v0.2)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-16
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_SCHEMA = "notification_schema"


def upgrade() -> None:
    op.drop_column("notification_preferences", "wechat_webhook_enc", schema=_SCHEMA)
    op.drop_column("notification_preferences", "dingtalk_webhook_enc", schema=_SCHEMA)


def downgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column("wechat_webhook_enc", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "notification_preferences",
        sa.Column("dingtalk_webhook_enc", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )
