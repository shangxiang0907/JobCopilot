from fastapi import FastAPI
from jobcopilot_shared.handlers import add_exception_handlers
from jobcopilot_shared.health import build_health_router
from jobcopilot_shared.logging import configure_logging
from jobcopilot_shared.metrics import instrument_app
from jobcopilot_shared.middleware.tenant import RequestContextMiddleware

from jobcopilot_profile.config import settings
from jobcopilot_profile.routers.admin import router as admin_router
from jobcopilot_profile.routers.internal import router as internal_router
from jobcopilot_profile.routers.profiles import router as profiles_router
from jobcopilot_profile.routers.resumes import router as resumes_router

configure_logging(settings.service_name)

app = FastAPI(
    title="Profile Service",
    description="User profiles, resume management, and credential storage",
    version=settings.version,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(RequestContextMiddleware)
instrument_app(app)
add_exception_handlers(app)

app.include_router(build_health_router(settings.service_name, settings.version))
app.include_router(admin_router)
app.include_router(profiles_router)
app.include_router(resumes_router)
app.include_router(internal_router)
