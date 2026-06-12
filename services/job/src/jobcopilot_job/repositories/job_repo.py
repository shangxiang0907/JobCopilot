import uuid
from datetime import UTC, datetime

from jobcopilot_shared.exceptions import ConflictError, NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_job.models.job import Job
from jobcopilot_job.schemas.job import InternalJobCreate, InternalJobUpdate, JobCreate, JobUpdate


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, tenant_id: uuid.UUID, data: JobCreate) -> Job:
        url = str(data.url)
        existing = await self._find_by_url(url)
        if existing is not None:
            raise ConflictError(f"Job with URL already exists: {url}")
        job = Job(
            tenant_id=tenant_id,
            company_id=data.company_id,
            title=data.title,
            company_name=data.company_name,
            url=url,
            source=data.source,
            raw_jd=data.raw_jd,
            salary_min=data.salary_min,
            salary_max=data.salary_max,
            location=data.location,
            job_type=data.job_type,
            discovered_at=datetime.now(UTC),
        )
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def create_internal(self, data: InternalJobCreate) -> Job:
        existing = await self._find_by_url(data.url)
        if existing is not None:
            raise ConflictError(f"Job with URL already exists: {data.url}")
        job = Job(
            tenant_id=data.tenant_id,
            company_id=data.company_id,
            title=data.title,
            company_name=data.company_name,
            url=data.url,
            source=data.source,
            raw_jd=data.raw_jd,
            analysis=data.analysis,
            salary_min=data.salary_min,
            salary_max=data.salary_max,
            location=data.location,
            job_type=data.job_type,
            discovered_at=data.discovered_at,
        )
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def get(self, tenant_id: uuid.UUID, job_id: uuid.UUID) -> Job:
        stmt = select(Job).where(Job.job_id == job_id, Job.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        job = result.scalar_one_or_none()
        if job is None:
            raise NotFoundError(f"Job {job_id} not found")
        return job

    async def get_internal(self, job_id: uuid.UUID) -> Job:
        """For internal service-to-service calls — no tenant filter."""
        stmt = select(Job).where(Job.job_id == job_id)
        result = await self._session.execute(stmt)
        job = result.scalar_one_or_none()
        if job is None:
            raise NotFoundError(f"Job {job_id} not found")
        return job

    async def get_all(
        self,
        tenant_id: uuid.UUID,
        page: int = 1,
        size: int = 20,
        source: str | None = None,
        location: str | None = None,
        job_type: str | None = None,
    ) -> tuple[list[Job], int]:
        from sqlalchemy import func as sqlfunc

        filters = [Job.tenant_id == tenant_id]
        if source:
            filters.append(Job.source == source)
        if location:
            filters.append(Job.location.ilike(f"%{location}%"))
        if job_type:
            filters.append(Job.job_type == job_type)

        total_stmt = select(sqlfunc.count()).select_from(
            select(Job.job_id).where(*filters).subquery()
        )
        total = (await self._session.execute(total_stmt)).scalar_one()

        rows_stmt = (
            select(Job)
            .where(*filters)
            .order_by(Job.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = list((await self._session.execute(rows_stmt)).scalars().all())
        return rows, total

    async def update(self, tenant_id: uuid.UUID, job_id: uuid.UUID, data: JobUpdate) -> Job:
        job = await self.get(tenant_id, job_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(job, field, value)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def update_internal(self, job_id: uuid.UUID, data: InternalJobUpdate) -> Job:
        job = await self.get_internal(job_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(job, field, value)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def delete(self, tenant_id: uuid.UUID, job_id: uuid.UUID) -> None:
        job = await self.get(tenant_id, job_id)
        await self._session.delete(job)
        await self._session.flush()

    async def _find_by_url(self, url: str) -> Job | None:
        stmt = select(Job).where(Job.url == url)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
