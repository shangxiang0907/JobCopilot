import uuid
from datetime import datetime
from typing import Any

from jobcopilot_shared.models.base import Base
from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

_TS = DateTime(timezone=True)
_SCHEMA = "notification_schema"


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # "cookie_expired" | "job_discovered" | "analysis_complete" | "reminder" | "custom"
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # "in_app" | "email" | "wechat" | "dingtalk"
    channel: Mapped[str] = mapped_column(String(32), nullable=False)

    # "pending" | "sent" | "failed"
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
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
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)

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
