from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from jobcopilot_shared.handlers import add_exception_handlers
from jobcopilot_shared.health import build_health_router
from jobcopilot_shared.logging import configure_logging
from jobcopilot_shared.middleware.tenant import RequestContextMiddleware

from jobcopilot_notification.config import settings
from jobcopilot_notification.routers.internal import router as internal_router
from jobcopilot_notification.routers.notifications import router as notifications_router
from jobcopilot_notification.services.consumer import start_consumer_background

configure_logging(settings.service_name)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    consumer_task = start_consumer_background()
    yield
    consumer_task.cancel()


app = FastAPI(
    title="Notification Service",
    description="Multi-channel notification dispatch: in-app, email, WeChat, DingTalk",
    version=settings.version,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
add_exception_handlers(app)

app.include_router(build_health_router(settings.service_name, settings.version))
app.include_router(notifications_router)
app.include_router(internal_router)
