from fastapi import APIRouter

from jobcopilot_shared.schemas.common import HealthResponse


def build_health_router(service_name: str, version: str = "0.1.0") -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/healthz/live", response_model=HealthResponse)
    async def liveness() -> HealthResponse:
        return HealthResponse(status="ok", service=service_name, version=version)

    @router.get("/healthz/ready", response_model=HealthResponse)
    async def readiness() -> HealthResponse:
        return HealthResponse(status="ok", service=service_name, version=version)

    return router
