import uuid
from datetime import datetime

from jobcopilot_shared.models.base import Base
from sqlalchemy import DateTime, PrimaryKeyConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

_SCHEMA = "job_schema"
_TS = DateTime(timezone=True)


class UserCompanyWatchlist(Base):
    __tablename__ = "user_company_watchlist"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "company_id"),
        {"schema": _SCHEMA},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), nullable=False)
