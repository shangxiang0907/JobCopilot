from fastapi import FastAPI
from jobcopilot_shared.handlers import add_exception_handlers
from jobcopilot_shared.health import build_health_router
from jobcopilot_shared.logging import configure_logging
from jobcopilot_shared.metrics import instrument_app
from jobcopilot_shared.middleware.tenant import RequestContextMiddleware

from jobcopilot_job.config import settings
from jobcopilot_job.routers.applications import router as applications_router
from jobcopilot_job.routers.companies import router as companies_router
from jobcopilot_job.routers.internal import router as internal_router
from jobcopilot_job.routers.jobs import router as jobs_router

configure_logging(settings.service_name)

app = FastAPI(
    title="Job Service",
    description="Job CRUD, Kanban, and Application Pipeline",
    version=settings.version,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(RequestContextMiddleware)
instrument_app(app)
add_exception_handlers(app)

app.include_router(build_health_router(settings.service_name, settings.version, settings.git_sha))
app.include_router(companies_router)
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(internal_router)
