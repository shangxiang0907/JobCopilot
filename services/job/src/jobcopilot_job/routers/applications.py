import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from jobcopilot_shared.schemas.common import PaginatedResponse

from jobcopilot_job.deps import SessionDep, TenantIdDep, UserIdDep
from jobcopilot_job.repositories.application_repo import ApplicationRepository
from jobcopilot_job.schemas.application import (
    ApplicationCreate,
    ApplicationEventResponse,
    ApplicationJobSummary,
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
    job_id: Annotated[uuid.UUID | None, Query()] = None,
) -> PaginatedResponse[ApplicationResponse]:
    repo = ApplicationRepository(session)
    rows, total = await repo.get_all(
        user_id, tenant_id, page=page, size=size, status=status_filter, job_id=job_id
    )
    items = []
    for app, job in rows:
        item = ApplicationResponse.model_validate(app)
        if job is not None:
            item.job = ApplicationJobSummary.model_validate(job)
        items.append(item)
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
    await session.commit()
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
    await session.commit()
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
    await session.commit()
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
    await session.commit()


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
