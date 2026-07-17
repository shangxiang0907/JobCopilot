from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends
from jobcopilot_shared.auth import TokenClaimsDep
from jobcopilot_shared.db import build_engine, build_session_factory
from jobcopilot_shared.exceptions import LLMKeyNotConfiguredError
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_agent.config import settings
from jobcopilot_agent.services.llm import (
    BYO_KEY_MISSING_MESSAGE,
    fetch_user_llm_key,
    set_request_llm_key,
)
from jobcopilot_agent.services.quota import enforce_daily_quota

_engine = build_engine(settings.database_url)
_session_factory = build_session_factory(_engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        yield session


@asynccontextmanager
async def open_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Session for non-request contexts (ReAct tools) sharing the app engine."""
    async with _session_factory() as session:
        yield session


async def get_current_user(claims: TokenClaimsDep) -> dict[str, Any]:
    return {
        "user_id": claims.sub,
        "tenant_id": claims.tenant_id,
    }


DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


async def provision_llm_key(user: CurrentUser) -> None:
    """Single chokepoint on every route that can trigger an LLM call (ADR-007).

    byo mode: bind the caller's stored key to this request's LLM calls; a user
    without a saved key gets a 409 llm_key_not_configured before any graph runs.
    platform mode: the env key (resolved inside services.llm) serves everyone,
    so each action counts against the tenant's daily quota — 429 quota_exceeded
    once spent. BYO users burn their own key and are never quota-limited.
    """
    if settings.llm_key_mode != "byo":
        await enforce_daily_quota(str(user["tenant_id"]))
        return
    key = await fetch_user_llm_key(str(user["user_id"]))
    if not key:
        raise LLMKeyNotConfiguredError(BYO_KEY_MISSING_MESSAGE)
    set_request_llm_key(key)


LLMKeyDep = Depends(provision_llm_key)
