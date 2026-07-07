import logging
import sys
from contextvars import ContextVar

import structlog

# Per-request context vars — set by RequestContextMiddleware
trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="-")
tenant_id_ctx: ContextVar[str] = ContextVar("tenant_id", default="-")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="-")


def configure_logging(service_name: str, level: str = "INFO") -> None:
    """Call once at service startup before the first log line.

    The whole chain is native structlog (PrintLogger → JSON on stdout);
    stdlib-only processors like `structlog.stdlib.add_logger_name` must not
    be used here — they require a `logging.Logger` and crash on PrintLogger.
    """

    def _add_service_context(
        logger: structlog.types.WrappedLogger,
        method_name: str,
        event_dict: structlog.types.EventDict,
    ) -> structlog.types.EventDict:
        event_dict.setdefault("service", service_name)
        event_dict.setdefault("trace_id", trace_id_ctx.get())
        event_dict.setdefault("tenant_id", tenant_id_ctx.get())
        event_dict.setdefault("user_id", user_id_ctx.get())
        return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_service_context,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )
    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.typing.FilteringBoundLogger:
    # PrintLogger carries no name, so bind it as the `logger` key — same key
    # `add_logger_name` would emit, keeping Loki/Grafana queries stable.
    logger: structlog.typing.FilteringBoundLogger = structlog.get_logger()
    return logger.bind(logger=name)
