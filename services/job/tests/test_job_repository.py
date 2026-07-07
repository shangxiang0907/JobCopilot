"""Integration tests: Job service — CRUD against a real PostgreSQL database.

Schema is created by `alembic upgrade head` (run as a CI step before pytest).
"""

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
from jobcopilot_job.repositories.job_repo import JobRepository
from jobcopilot_job.schemas.job import InternalJobCreate
from jobcopilot_shared.db import build_engine, build_session_factory
from jobcopilot_shared.exceptions import NotFoundError
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = build_engine(os.environ["DATABASE_URL"])
    yield engine
    await engine.dispose()


@pytest.mark.integration
async def test_job_create_and_get(db_engine: AsyncEngine) -> None:
    factory = build_session_factory(db_engine)
    tenant_id = uuid.uuid4()
    async with factory() as session:
        async with session.begin():
            job = await JobRepository(session).create_internal(
                InternalJobCreate(
                    tenant_id=tenant_id,
                    title="Senior Python Engineer",
                    company_name="Acme Corp",
                    url=f"https://linkedin.com/jobs/view/{uuid.uuid4()}",
                    source="linkedin",
                    location="Remote",
                    job_type="full_time",
                )
            )
            job_id = job.job_id
            assert job.title == "Senior Python Engineer"
            assert job.tenant_id == tenant_id

    async with factory() as session:
        async with session.begin():
            fetched = await JobRepository(session).get(tenant_id, job_id)
            assert fetched.company_name == "Acme Corp"
            assert fetched.location == "Remote"


@pytest.mark.integration
async def test_job_tenant_isolation(db_engine: AsyncEngine) -> None:
    factory = build_session_factory(db_engine)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    async with factory() as session:
        async with session.begin():
            job = await JobRepository(session).create_internal(
                InternalJobCreate(
                    tenant_id=tenant_a,
                    title="Isolated Job",
                    company_name="Corp A",
                    url=f"https://linkedin.com/jobs/view/{uuid.uuid4()}",
                    source="linkedin",
                )
            )
            job_id = job.job_id

    async with factory() as session:
        async with session.begin():
            with pytest.raises(NotFoundError):
                await JobRepository(session).get(tenant_b, job_id)


@pytest.mark.integration
async def test_job_delete(db_engine: AsyncEngine) -> None:
    factory = build_session_factory(db_engine)
    tenant_id = uuid.uuid4()
    async with factory() as session:
        async with session.begin():
            job = await JobRepository(session).create_internal(
                InternalJobCreate(
                    tenant_id=tenant_id,
                    title="Job To Delete",
                    company_name="Corp",
                    url=f"https://linkedin.com/jobs/view/{uuid.uuid4()}",
                    source="linkedin",
                )
            )
            job_id = job.job_id

    async with factory() as session:
        async with session.begin():
            await JobRepository(session).delete(tenant_id, job_id)

    async with factory() as session:
        async with session.begin():
            with pytest.raises(NotFoundError):
                await JobRepository(session).get(tenant_id, job_id)


@pytest.mark.integration
async def test_job_search_filter(db_engine: AsyncEngine) -> None:
    factory = build_session_factory(db_engine)
    tenant_id = uuid.uuid4()
    async with factory() as session:
        async with session.begin():
            repo = JobRepository(session)
            for title, company in [
                ("Senior Python Engineer", "Acme Corp"),
                ("Data Scientist", "Beta Labs"),
            ]:
                await repo.create_internal(
                    InternalJobCreate(
                        tenant_id=tenant_id,
                        title=title,
                        company_name=company,
                        url=f"https://linkedin.com/jobs/view/{uuid.uuid4()}",
                        source="linkedin",
                    )
                )

    async with factory() as session:
        async with session.begin():
            repo = JobRepository(session)
            by_title, total_title = await repo.get_all(tenant_id, search="python")
            assert total_title == 1
            assert by_title[0].title == "Senior Python Engineer"

            by_company, total_company = await repo.get_all(tenant_id, search="beta")
            assert total_company == 1
            assert by_company[0].company_name == "Beta Labs"

            none_found, total_none = await repo.get_all(tenant_id, search="golang")
            assert total_none == 0
            assert none_found == []


@pytest.mark.integration
async def test_internal_create_is_idempotent_upsert_by_url(db_engine: AsyncEngine) -> None:
    """Discovery re-runs re-publish the same URL — the second create must return
    the SAME job (refreshed), not raise ConflictError."""
    factory = build_session_factory(db_engine)
    tenant_id = uuid.uuid4()
    url = f"https://linkedin.com/jobs/view/{uuid.uuid4()}"

    async with factory() as session:
        async with session.begin():
            first = await JobRepository(session).create_internal(
                InternalJobCreate(
                    tenant_id=tenant_id,
                    title="Backend Engineer",
                    company_name="Acme",
                    url=url,
                    source="discovery",
                )
            )
            first_id = first.job_id

    async with factory() as session:
        async with session.begin():
            second = await JobRepository(session).create_internal(
                InternalJobCreate(
                    tenant_id=tenant_id,
                    title="Backend Engineer",
                    company_name="Acme",
                    url=url,
                    source="discovery",
                    raw_jd="fresh description",
                    analysis={"skills_required": ["Python"]},
                )
            )
            assert second.job_id == first_id
            assert second.raw_jd == "fresh description"
            assert second.analysis == {"skills_required": ["Python"]}
