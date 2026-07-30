import uuid
from collections.abc import Awaitable, Callable

import structlog
from jose import jwt as jose_jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from jobcopilot_shared.logging import tenant_id_ctx, trace_id_ctx, user_id_ctx
from jobcopilot_shared.metrics import record_degradation

logger = structlog.get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Decodes JWT payload (without signature verification) to bind sub/tenant_id
    into structlog context for logging. Security verification happens in route
    dependencies via jobcopilot_shared.auth.verify_token."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        user_id = "-"
        tenant_id = "-"
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            try:
                token = auth.split(" ", 1)[1]
                payload = jose_jwt.get_unverified_claims(token)
                user_id = payload.get("sub", "-")
                tenant_id = payload.get("tenant_id", "-")
            except Exception as exc:  # noqa: BLE001 — logging context, never a security gate
                # Continuing is correct: this middleware only enriches log
                # context, and route dependencies still verify the signature —
                # an unreadable token gets rejected there, not here. But "-" as
                # a tenant means the logs cannot attribute the request, so the
                # cause is recorded rather than swallowed. The exception type
                # only: the token itself must never reach the log.
                logger.warning("request_context_token_unreadable", error_type=type(exc).__name__)
                record_degradation(operation="request_context", reason="token_unreadable")

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
