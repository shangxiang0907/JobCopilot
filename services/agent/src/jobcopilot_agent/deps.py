import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends
from jobcopilot_shared.auth import TokenClaimsDep
from jobcopilot_shared.db import build_engine, build_session_factory
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_agent.config import settings

_engine = build_engine(settings.database_url)
_session_factory = build_session_factory(_engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        yield session


async def get_current_user(claims: TokenClaimsDep) -> dict[str, Any]:
    return {
        "user_id": claims.sub,
        "tenant_id": claims.tenant_id,
    }


DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]
