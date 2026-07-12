import uuid
from datetime import datetime
from typing import Any

from jobcopilot_shared.models.base import Base
from sqlalchemy import DateTime, Index, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

_SCHEMA = "profile_schema"
_TS = DateTime(timezone=True)


class Profile(Base):
    __tablename__ = "profiles"
    # Names must match migration 0001 / the live DB exactly (alembic check).
    __table_args__ = (
        UniqueConstraint("user_id", name="profiles_user_id_key"),
        Index("ix_profiles_user_id", "user_id"),
        {"schema": _SCHEMA},
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    personal_info: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    preferences: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # AES-256-GCM encrypted; never returned in external API responses
    llm_api_key_enc: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        _TS, server_default=func.now(), onupdate=func.now(), nullable=False
    )
