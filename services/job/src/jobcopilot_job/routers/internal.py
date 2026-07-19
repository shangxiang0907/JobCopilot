"""Internal routes — accessible via K8s DNS only. Kong blocks external access."""

import uuid

from fastapi import APIRouter, Query, status
from jobcopilot_shared.exceptions import NotFoundError
from jobcopilot_shared.schemas.common import PaginatedResponse

from jobcopilot_job.deps import SessionDep
from jobcopilot_job.repositories.application_repo import ApplicationRepository
from jobcopilot_job.repositories.job_repo import JobRepository
from jobcopilot_job.schemas.application import (
    ApplicationJobSummary,
    ApplicationResponse,
    ApplicationStatusUpdate,
    InternalAnalysisUpdate,
    InternalKanbanUpdate,
)
from jobcopilot_job.schemas.job import InternalJobCreate, InternalJobUpdate, JobResponse

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/jobs", response_model=PaginatedResponse[JobResponse])
async def internal_list_jobs(
    session: SessionDep,
    tenant_id: uuid.UUID,
    q: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=50),
) -> PaginatedResponse[JobResponse]:
    """List/search jobs for a tenant — used by the Agent Service search_jobs tool."""
    repo = JobRepository(session)
    jobs, total = await repo.get_all(tenant_id, page=1, size=limit, search=q)
    items = [JobResponse.model_validate(j) for j in jobs]
    return PaginatedResponse(items=items, total=total, page=1, size=limit, has_next=limit < total)


@router.get("/applications", response_model=PaginatedResponse[ApplicationResponse])
async def internal_list_applications(
    session: SessionDep,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=10, ge=1, le=50),
) -> PaginatedResponse[ApplicationResponse]:
    """List a user's applications — used by the Agent Service get_applications tool."""
    repo = ApplicationRepository(session)
    rows, total = await repo.get_all(user_id, tenant_id, page=1, size=limit, status=status_filter)
    items = []
    for app, job in rows:
        item = ApplicationResponse.model_validate(app)
        if job is not None:
            item.job = ApplicationJobSummary.model_validate(job)
        items.append(item)
    return PaginatedResponse(items=items, total=total, page=1, size=limit, has_next=limit < total)


@router.patch("/applications/by-job/{job_id}", response_model=ApplicationResponse)
async def internal_transition_application_by_job(
    job_id: uuid.UUID,
    body: InternalKanbanUpdate,
    session: SessionDep,
) -> ApplicationResponse:
    """Move a user's application for a job to a new status — used by update_kanban."""
    repo = ApplicationRepository(session)
    rows, _total = await repo.get_all(body.user_id, body.tenant_id, page=1, size=1, job_id=job_id)
    if not rows:
        raise NotFoundError(f"No application found for job {job_id}")
    app, _job = rows[0]
    app = await repo.transition_status(
        body.user_id,
        app.application_id,
        ApplicationStatusUpdate(status=body.status, note=body.note),
    )
    await session.commit()
    return ApplicationResponse.model_validate(app)


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_200_OK)
async def internal_create_job(
    body: InternalJobCreate,
    session: SessionDep,
) -> JobResponse:
    """Idempotent upsert by URL: returns the existing job (refreshed with any new
    raw_jd/analysis) instead of 409 — discovery re-runs re-publish the same URLs.
    Callers rely on job_id in the response to key their own records."""
    repo = JobRepository(session)
    job = await repo.create_internal(body)
    # Callers key their records off the returned job_id — it must be committed
    # (visible) before they act on it.
    await session.commit()
    return JobResponse.model_validate(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def internal_get_job(
    job_id: uuid.UUID,
    session: SessionDep,
) -> JobResponse:
    repo = JobRepository(session)
    job = await repo.get_internal(job_id)
    return JobResponse.model_validate(job)


@router.patch("/jobs/{job_id}", response_model=JobResponse)
async def internal_update_job(
    job_id: uuid.UUID,
    body: InternalJobUpdate,
    session: SessionDep,
) -> JobResponse:
    repo = JobRepository(session)
    job = await repo.update_internal(job_id, body)
    await session.commit()
    return JobResponse.model_validate(job)


@router.patch("/applications/{application_id}/analysis", response_model=ApplicationResponse)
async def internal_update_application_analysis(
    application_id: uuid.UUID,
    body: InternalAnalysisUpdate,
    session: SessionDep,
) -> ApplicationResponse:
    repo = ApplicationRepository(session)
    app = await repo.update_analysis(application_id, body)
    await session.commit()
    return ApplicationResponse.model_validate(app)
