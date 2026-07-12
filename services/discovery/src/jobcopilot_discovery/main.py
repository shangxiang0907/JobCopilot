from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from jobcopilot_shared.handlers import add_exception_handlers
from jobcopilot_shared.health import build_health_router
from jobcopilot_shared.logging import configure_logging
from jobcopilot_shared.metrics import instrument_app
from jobcopilot_shared.middleware.tenant import RequestContextMiddleware

from jobcopilot_discovery.config import settings
from jobcopilot_discovery.routers.configs import router as configs_router
from jobcopilot_discovery.routers.runs import router as runs_router
from jobcopilot_discovery.worker.worker import start_worker_background

configure_logging(settings.service_name)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    worker_task = start_worker_background()
    yield
    worker_task.cancel()


app = FastAPI(
    title="Discovery Service",
    description="Public-source job discovery via Temporal (ADR-006)",
    version=settings.version,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
instrument_app(app)
add_exception_handlers(app)

app.include_router(build_health_router(settings.service_name, settings.version))
app.include_router(configs_router)
app.include_router(runs_router)
