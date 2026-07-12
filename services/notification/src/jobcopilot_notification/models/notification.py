import uuid
from datetime import datetime
from typing import Any

from jobcopilot_shared.models.base import Base
from sqlalchemy import Boolean, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

_TS = DateTime(timezone=True)
_SCHEMA = "notification_schema"


class Notification(Base):
    __tablename__ = "notifications"
    # Names must match migration 0001 / the live DB exactly (alembic check).
    __table_args__ = (
        Index("ix_notifications_tenant_id", "tenant_id"),
        Index("ix_notifications_user_id", "user_id"),
        Index("ix_notifications_status", "status"),
        {"schema": _SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # "cookie_expired" | "job_discovered" | "analysis_complete" | "reminder" | "custom"
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # "in_app" | "email" | "wechat" | "dingtalk"
    channel: Mapped[str] = mapped_column(String(32), nullable=False)

    # "pending" | "sent" | "failed"
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Extra context (job_id, run_id, etc.)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    # In-app read tracking
    read_at: Mapped[datetime | None] = mapped_column(_TS, nullable=True)

    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        _TS, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    # Names must match migration 0001 / the live DB exactly (alembic check):
    # user_id uniqueness lives in a UNIQUE INDEX, not a table constraint.
    __table_args__ = (
        Index("ix_notification_preferences_user_id", "user_id", unique=True),
        Index("ix_notification_preferences_tenant_id", "tenant_id"),
        {"schema": _SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_address: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Stored AES-256-GCM encrypted
    wechat_webhook_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    dingtalk_webhook_enc: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        _TS, server_default=func.now(), onupdate=func.now(), nullable=False
    )
