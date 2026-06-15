import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from jobcopilot_shared.auth import TokenClaimsDep
from jobcopilot_shared.db import build_engine, build_session_factory
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_discovery.config import settings

_engine = build_engine(settings.database_url)
_session_factory = build_session_factory(_engine)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        async with session.begin():
            yield session


async def get_user_id(claims: TokenClaimsDep) -> uuid.UUID:
    return claims.sub


async def get_tenant_id(claims: TokenClaimsDep) -> uuid.UUID:
    return claims.tenant_id


SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserIdDep = Annotated[uuid.UUID, Depends(get_user_id)]
TenantIdDep = Annotated[uuid.UUID, Depends(get_tenant_id)]
