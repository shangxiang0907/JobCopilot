"""Internal routes — accessible via K8s DNS only. Kong blocks external access."""

import uuid

from fastapi import APIRouter, status

from app.deps import SessionDep
from app.repositories.application_repo import ApplicationRepository
from app.repositories.job_repo import JobRepository
from app.schemas.application import ApplicationResponse, InternalAnalysisUpdate
from app.schemas.job import InternalJobCreate, InternalJobUpdate, JobResponse

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def internal_create_job(
    body: InternalJobCreate,
    session: SessionDep,
) -> JobResponse:
    repo = JobRepository(session)
    job = await repo.create_internal(body)
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
    return JobResponse.model_validate(job)


@router.patch("/applications/{application_id}/analysis", response_model=ApplicationResponse)
async def internal_update_application_analysis(
    application_id: uuid.UUID,
    body: InternalAnalysisUpdate,
    session: SessionDep,
) -> ApplicationResponse:
    repo = ApplicationRepository(session)
    app = await repo.update_analysis(application_id, body)
    return ApplicationResponse.model_validate(app)
