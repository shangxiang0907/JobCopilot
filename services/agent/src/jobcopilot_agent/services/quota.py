"""Per-tenant daily AI-action quota — the cost gate for platform key mode.

Open registration + a platform LLM key means any user could otherwise run
unbounded AI actions on the operator's DashScope bill. Kong's rate limit is
transport-layer (requests/minute) and does not cap daily spend; this counter
does. One quota unit = one request to an LLM route (analyze / match /
interview / chat message — a chat message with screenshots still counts once,
its vision fan-out is bounded in the chat router).

The counter lives in Redis keyed `quota:llm:{tenant_id}:{YYYYMMDD}` (UTC) and
expires on its own. Redis being down fails CLOSED (503 quota_unavailable):
this is cost enforcement, not traffic smoothing — unmetered spend on the
operator's key is worse than AI features pausing until Redis returns. BYO
deployments never reach this check, and platform operators can drop the
Redis dependency entirely with LLM_DAILY_QUOTA <= 0.
"""

import logging
from datetime import UTC, datetime

from jobcopilot_shared.exceptions import QuotaExceededError, QuotaUnavailableError
from jobcopilot_shared.redis_client import build_redis

from jobcopilot_agent.config import settings

log = logging.getLogger(__name__)

_redis = build_redis(settings.redis_url)

# Keys are per-day; keep them long enough to observe yesterday, then self-clean.
_KEY_TTL_SECONDS = 48 * 60 * 60

QUOTA_EXCEEDED_MESSAGE = (
    "Daily AI quota reached ({quota} AI actions per day). The quota resets at midnight UTC."
)

QUOTA_UNAVAILABLE_MESSAGE = "AI features are temporarily unavailable. Please try again shortly."


def _quota_key(tenant_id: str) -> str:
    return f"quota:llm:{tenant_id}:{datetime.now(tz=UTC):%Y%m%d}"


async def enforce_daily_quota(tenant_id: str) -> None:
    """Count this AI action and raise 429 quota_exceeded once the day's cap is hit.

    Rejected requests keep incrementing the counter (they never reach an LLM,
    so the check stays `> quota` and over-count is harmless attempt telemetry).
    """
    quota = settings.llm_daily_quota
    if quota <= 0:
        return
    try:
        used = int(await _redis.incr(_quota_key(tenant_id)))
        if used == 1:
            await _redis.expire(_quota_key(tenant_id), _KEY_TTL_SECONDS)
    except Exception as exc:
        log.error("quota_accounting_unavailable_failing_closed: %s", exc)
        raise QuotaUnavailableError(QUOTA_UNAVAILABLE_MESSAGE) from exc
    if used > quota:
        raise QuotaExceededError(QUOTA_EXCEEDED_MESSAGE.format(quota=quota))
