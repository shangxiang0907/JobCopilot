import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from jobcopilot_shared.db import build_engine, build_session_factory
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

_engine = build_engine(settings.database_url)
_session_factory = build_session_factory(_engine)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        async with session.begin():
            yield session


async def _require_header(value: str | None, name: str) -> str:
    if not value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing {name} header",
        )
    return value


async def get_user_id(x_user_id: Annotated[str | None, Header()] = None) -> uuid.UUID:
    value = await _require_header(x_user_id, "X-User-Id")
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-User-Id format",
        ) from exc


async def get_tenant_id(x_tenant_id: Annotated[str | None, Header()] = None) -> uuid.UUID:
    value = await _require_header(x_tenant_id, "X-Tenant-Id")
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Tenant-Id format",
        ) from exc


SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserIdDep = Annotated[uuid.UUID, Depends(get_user_id)]
TenantIdDep = Annotated[uuid.UUID, Depends(get_tenant_id)]
