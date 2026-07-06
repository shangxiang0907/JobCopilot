"""Integration tests: Application repository — list with job join + job_id filter.

Schema is created by `alembic upgrade head` (run as a CI step before pytest).
"""

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
from jobcopilot_job.repositories.application_repo import ApplicationRepository
from jobcopilot_job.repositories.job_repo import JobRepository
from jobcopilot_job.schemas.application import ApplicationCreate
from jobcopilot_job.schemas.job import InternalJobCreate
from jobcopilot_shared.db import build_engine, build_session_factory
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = build_engine(os.environ["DATABASE_URL"])
    yield engine
    await engine.dispose()


async def _seed_job(session: AsyncSession, tenant_id: uuid.UUID, title: str) -> uuid.UUID:
    job = await JobRepository(session).create_internal(
        InternalJobCreate(
            tenant_id=tenant_id,
            title=title,
            company_name="Acme Corp",
            url=f"https://linkedin.com/jobs/view/{uuid.uuid4()}",
            source="linkedin",
            location="Remote",
            job_type="full_time",
        )
    )
    return job.job_id


@pytest.mark.integration
async def test_get_all_embeds_job_and_filters_by_job_id(db_engine: AsyncEngine) -> None:
    factory = build_session_factory(db_engine)
    tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

    async with factory() as session:
        async with session.begin():
            job_a = await _seed_job(session, tenant_id, "Job A")
            job_b = await _seed_job(session, tenant_id, "Job B")
            repo = ApplicationRepository(session)
            await repo.create(user_id, ApplicationCreate(job_id=job_a))
            await repo.create(user_id, ApplicationCreate(job_id=job_b))

    async with factory() as session:
        async with session.begin():
            repo = ApplicationRepository(session)

            rows, total = await repo.get_all(user_id, tenant_id)
            assert total == 2
            titles = {job.title for _, job in rows if job is not None}
            assert titles == {"Job A", "Job B"}

            rows, total = await repo.get_all(user_id, tenant_id, job_id=job_a)
            assert total == 1
            app, job = rows[0]
            assert app.job_id == job_a
            assert job is not None and job.title == "Job A"


@pytest.mark.integration
async def test_get_all_job_join_respects_tenant(db_engine: AsyncEngine) -> None:
    """A job belonging to another tenant must not be joined onto the application."""
    factory = build_session_factory(db_engine)
    tenant_a, tenant_b, user_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    async with factory() as session:
        async with session.begin():
            job_id = await _seed_job(session, tenant_a, "Cross-tenant Job")
            await ApplicationRepository(session).create(user_id, ApplicationCreate(job_id=job_id))

    async with factory() as session:
        async with session.begin():
            rows, total = await ApplicationRepository(session).get_all(user_id, tenant_b)
            assert total == 1
            app, job = rows[0]
            assert app.job_id == job_id
            assert job is None
