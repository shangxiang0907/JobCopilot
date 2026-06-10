import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from jobcopilot_shared.logging import tenant_id_ctx, trace_id_ctx, user_id_ctx

logger = structlog.get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Extracts tenant_id and user_id from headers set by the Kong JWT plugin,
    binds them into context vars for downstream logging and DB query guards."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Kong's JWT validation plugin injects these after token verification
        tenant_id = request.headers.get("X-Tenant-Id", "-")
        user_id = request.headers.get("X-User-Id", "-")
        trace_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())

        tenant_id_ctx.set(tenant_id)
        user_id_ctx.set(user_id)
        trace_id_ctx.set(trace_id)

        structlog.contextvars.bind_contextvars(
            trace_id=trace_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        response = await call_next(request)
        response.headers["X-Request-Id"] = trace_id

        structlog.contextvars.clear_contextvars()
        return response
