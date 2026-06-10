import uuid

from fastapi import APIRouter, Query, status
from jobcopilot_shared.schemas.common import PaginatedResponse

from app.deps import SessionDep, TenantIdDep, UserIdDep
from app.repositories.application_repo import ApplicationRepository
from app.schemas.application import (
    ApplicationCreate,
    ApplicationEventResponse,
    ApplicationResponse,
    ApplicationStatusUpdate,
    ApplicationUpdate,
)

router = APIRouter(prefix="/v1/applications", tags=["applications"])


@router.get("", response_model=PaginatedResponse[ApplicationResponse])
async def list_applications(
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
    page: int = 1,
    size: int = 20,
    status_filter: str | None = Query(default=None, alias="status"),
) -> PaginatedResponse[ApplicationResponse]:
    repo = ApplicationRepository(session)
    apps, total = await repo.list(user_id, page=page, size=size, status=status_filter)
    items = [ApplicationResponse.model_validate(a) for a in apps]
    return PaginatedResponse(
        items=items, total=total, page=page, size=size, has_next=(page * size < total)
    )


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    body: ApplicationCreate,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> ApplicationResponse:
    repo = ApplicationRepository(session)
    app = await repo.create(user_id, body)
    return ApplicationResponse.model_validate(app)


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: uuid.UUID,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> ApplicationResponse:
    repo = ApplicationRepository(session)
    app = await repo.get(user_id, application_id)
    return ApplicationResponse.model_validate(app)


@router.patch("/{application_id}/status", response_model=ApplicationResponse)
async def transition_application_status(
    application_id: uuid.UUID,
    body: ApplicationStatusUpdate,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> ApplicationResponse:
    repo = ApplicationRepository(session)
    app = await repo.transition_status(user_id, application_id, body)
    return ApplicationResponse.model_validate(app)


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: uuid.UUID,
    body: ApplicationUpdate,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> ApplicationResponse:
    repo = ApplicationRepository(session)
    app = await repo.update_notes(user_id, application_id, body)
    return ApplicationResponse.model_validate(app)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: uuid.UUID,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> None:
    repo = ApplicationRepository(session)
    await repo.delete(user_id, application_id)


@router.get("/{application_id}/events", response_model=list[ApplicationEventResponse])
async def get_application_events(
    application_id: uuid.UUID,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> list[ApplicationEventResponse]:
    repo = ApplicationRepository(session)
    events = await repo.get_events(user_id, application_id)
    return [ApplicationEventResponse.model_validate(e) for e in events]
