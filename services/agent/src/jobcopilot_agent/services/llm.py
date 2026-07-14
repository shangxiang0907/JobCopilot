"""LLM client factory — API key resolved by deployment mode (ADR-007).

platform: the deployment-wide DASHSCOPE_API_KEY serves every request.
byo:      each request carries the calling user's decrypted key, set by the
          provision_llm_key dependency at the route entry; graphs, ReAct tools
          and vision transcription inherit it through the request context.
"""

from contextvars import ContextVar
from functools import lru_cache

import httpx
from jobcopilot_shared.exceptions import LLMKeyNotConfiguredError
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from jobcopilot_agent.config import settings

BYO_KEY_MISSING_MESSAGE = (
    "No LLM API key configured. Save your OpenAI-compatible API key under "
    "Profile → Credentials to use AI features."
)

_request_llm_key: ContextVar[str | None] = ContextVar("request_llm_key", default=None)


def set_request_llm_key(key: str) -> None:
    """Bind the caller's decrypted key to the current request context (byo mode)."""
    _request_llm_key.set(key)


async def fetch_user_llm_key(user_id: str) -> str | None:
    """Decrypted per-user key from the Profile Service internal API (byo mode)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{settings.profile_service_url}/internal/profiles/{user_id}")
    if resp.status_code != 200:
        return None
    key = resp.json().get("llm_api_key")
    return str(key) if key else None


def _resolve_api_key() -> str:
    if settings.llm_key_mode == "platform":
        return settings.dashscope_api_key or "placeholder"
    key = _request_llm_key.get()
    if not key:
        raise LLMKeyNotConfiguredError(BYO_KEY_MISSING_MESSAGE)
    return key


@lru_cache(maxsize=32)
def _chat_model(model: str, api_key: str, temperature: float) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=SecretStr(api_key),
        base_url=settings.dashscope_base_url,
        temperature=temperature,
    )


def get_llm() -> ChatOpenAI:
    return _chat_model(settings.llm_model, _resolve_api_key(), 0.1)


def get_vision_llm() -> ChatOpenAI:
    """Multimodal model for JD screenshot transcription (PRD 3.1 entry #3)."""
    return _chat_model(settings.llm_vision_model, _resolve_api_key(), 0.0)
