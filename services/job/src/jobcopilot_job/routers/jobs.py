import uuid

from fastapi import APIRouter, Query, status
from jobcopilot_shared.schemas.common import PaginatedResponse

from jobcopilot_job.deps import SessionDep, TenantIdDep
from jobcopilot_job.repositories.job_repo import JobRepository
from jobcopilot_job.schemas.job import JobCreate, JobResponse, JobUpdate

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


@router.get("", response_model=PaginatedResponse[JobResponse])
async def list_jobs(
    session: SessionDep,
    tenant_id: TenantIdDep,
    page: int = 1,
    size: int = 20,
    source: str | None = Query(default=None),
    location: str | None = Query(default=None),
    job_type: str | None = Query(default=None),
) -> PaginatedResponse[JobResponse]:
    repo = JobRepository(session)
    jobs, total = await repo.get_all(
        tenant_id, page=page, size=size, source=source, location=location, job_type=job_type
    )
    items = [JobResponse.model_validate(j) for j in jobs]
    return PaginatedResponse(
        items=items, total=total, page=page, size=size, has_next=(page * size < total)
    )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: JobCreate,
    session: SessionDep,
    tenant_id: TenantIdDep,
) -> JobResponse:
    repo = JobRepository(session)
    job = await repo.create(tenant_id, body)
    await session.commit()
    return JobResponse.model_validate(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    session: SessionDep,
    tenant_id: TenantIdDep,
) -> JobResponse:
    repo = JobRepository(session)
    job = await repo.get(tenant_id, job_id)
    return JobResponse.model_validate(job)


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: uuid.UUID,
    body: JobUpdate,
    session: SessionDep,
    tenant_id: TenantIdDep,
) -> JobResponse:
    repo = JobRepository(session)
    job = await repo.update(tenant_id, job_id, body)
    await session.commit()
    return JobResponse.model_validate(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    session: SessionDep,
    tenant_id: TenantIdDep,
) -> None:
    repo = JobRepository(session)
    await repo.delete(tenant_id, job_id)
    await session.commit()
