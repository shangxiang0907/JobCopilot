"""Provider-side LLM key validation at save time (byo mode).

A wrong key must fail when the user saves it, not on their first AI action.
`GET {base_url}/models` is the cheapest authenticated call on every
OpenAI-compatible endpoint (DashScope included) — zero tokens consumed.
"""

import httpx
from jobcopilot_shared.exceptions import ExternalServiceError, ValidationError

from jobcopilot_profile.config import settings


async def validate_llm_key(api_key: str) -> None:
    """Raise unless the provider accepts this key for the deployment's endpoint."""
    url = settings.dashscope_base_url.rstrip("/") + "/models"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
    except httpx.HTTPError as exc:
        raise ExternalServiceError(
            "Could not reach the LLM provider to verify the key; please try again"
        ) from exc
    if resp.status_code in (401, 403):
        raise ValidationError(
            "The LLM provider rejected this API key — check the key and try again"
        )
    if resp.status_code >= 400:
        raise ExternalServiceError(
            f"The LLM provider returned HTTP {resp.status_code} while verifying the key"
        )
