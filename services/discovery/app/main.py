from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from jobcopilot_shared.handlers import add_exception_handlers
from jobcopilot_shared.health import build_health_router
from jobcopilot_shared.logging import configure_logging
from jobcopilot_shared.middleware.tenant import RequestContextMiddleware

from app.config import settings
from app.routers.configs import router as configs_router
from app.routers.runs import router as runs_router
from app.worker.worker import start_worker_background

configure_logging(settings.service_name)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    worker_task = start_worker_background()
    yield
    worker_task.cancel()


app = FastAPI(
    title="Discovery Service",
    description="LinkedIn job discovery via Playwright + Temporal",
    version=settings.version,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
add_exception_handlers(app)

app.include_router(build_health_router(settings.service_name, settings.version))
app.include_router(configs_router)
app.include_router(runs_router)
