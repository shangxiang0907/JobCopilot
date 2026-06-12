import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status
from jobcopilot_shared.db import build_engine, build_session_factory
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_agent.config import settings

_engine = build_engine(settings.database_url)
_session_factory = build_session_factory(_engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        yield session


async def get_current_user(
    x_user_id: Annotated[str, Header(alias="X-User-Id")],
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-Id")],
) -> dict[str, Any]:
    try:
        return {
            "user_id": uuid.UUID(x_user_id),
            "tenant_id": uuid.UUID(x_tenant_id),
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user or tenant ID",
        ) from exc


DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]
