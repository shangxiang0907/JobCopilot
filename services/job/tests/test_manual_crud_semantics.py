"""Manual CRUD (PRD v0.3 Core layer) must be able to CLEAR a field, not only set it.

The v0.2 update schemas dumped with `exclude_none`, which silently collapses
"the caller left this alone" and "the caller wants this emptied" into the same
request. Through an edit form that reads as a bug with no trace: the user clears
the salary, saves, and the old number comes back — no error, no log line, no
metric. These tests pin the distinction, plus the two conflicts a manual editor
can now provoke (duplicate company name, duplicate job URL) and the dangling
company_id that deleting a company would otherwise leave behind.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from jobcopilot_job.models.company import Company
from jobcopilot_job.models.job import Job
from jobcopilot_job.repositories.company_repo import CompanyRepository
from jobcopilot_job.repositories.job_repo import JobRepository
from jobcopilot_job.schemas.company import CompanyCreate, CompanyUpdate
from jobcopilot_job.schemas.job import JobUpdate
from jobcopilot_shared.exceptions import ConflictError
from pydantic import HttpUrl, ValidationError

_TENANT = uuid.uuid4()


def _session(*results: object) -> AsyncMock:
    """A mock session whose execute() returns each given result in turn."""
    session = AsyncMock()
    session.add = MagicMock()  # Session.add is sync — AsyncMock leaves a coroutine unawaited
    session.execute = AsyncMock(side_effect=list(results))
    return session


def _result(scalar: object = None, rowcount: int = 0) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=scalar)
    result.rowcount = rowcount
    return result


def _job(**overrides: object) -> Job:
    defaults: dict[str, object] = {
        "job_id": uuid.uuid4(),
        "tenant_id": _TENANT,
        "title": "Backend Engineer",
        "company_name": "Acme",
        "url": "https://example.com/jobs/1",
        "source": "manual",
        "location": "Berlin",
        "salary_min": 60000,
    }
    return Job(**(defaults | overrides))


# ── omitted vs explicitly null ───────────────────────────────────────────────


def test_omitted_field_is_not_in_the_patch() -> None:
    patch = JobUpdate(title="New title").model_dump(exclude_unset=True)
    assert patch == {"title": "New title"}


def test_explicit_null_survives_into_the_patch() -> None:
    """This is the whole point: `null` must reach the repository as a value."""
    patch = JobUpdate(location=None, salary_min=None).model_dump(exclude_unset=True)
    assert patch == {"location": None, "salary_min": None}


@pytest.mark.asyncio
async def test_repository_clears_a_field_on_explicit_null() -> None:
    job = _job()
    repo = JobRepository(_session(_result(scalar=job)))

    await repo.update(_TENANT, job.job_id, JobUpdate(location=None))

    assert job.location is None
    assert job.salary_min == 60000, "an omitted field must be left alone"


@pytest.mark.parametrize("field", ["title", "company_name", "url"])
def test_not_null_columns_reject_an_explicit_null(field: str) -> None:
    """Better a 422 naming the field than an IntegrityError surfacing as a 500."""
    with pytest.raises(ValidationError, match="cannot be cleared"):
        JobUpdate(**{field: None})


@pytest.mark.parametrize("field", ["name", "is_blacklisted"])
def test_company_not_null_columns_reject_an_explicit_null(field: str) -> None:
    with pytest.raises(ValidationError, match="cannot be cleared"):
        CompanyUpdate(**{field: None})


@pytest.mark.parametrize("blank", ["", "   "])
def test_required_text_cannot_be_whitespace(blank: str) -> None:
    with pytest.raises(ValidationError):
        JobUpdate(title=blank)


def test_unknown_job_type_is_rejected_on_update_too() -> None:
    """JobCreate validated job_type; JobUpdate did not, so edits could bypass it."""
    with pytest.raises(ValidationError, match="job_type must be one of"):
        JobUpdate(job_type="freelance")


# ── conflicts a manual editor can provoke ────────────────────────────────────


@pytest.mark.asyncio
async def test_duplicate_company_name_is_a_conflict_not_an_integrity_error() -> None:
    existing = Company(company_id=uuid.uuid4(), tenant_id=_TENANT, name="Acme")
    repo = CompanyRepository(_session(_result(scalar=existing)))

    with pytest.raises(ConflictError, match="already exists"):
        await repo.create(_TENANT, CompanyCreate(name="  acme "))


@pytest.mark.asyncio
async def test_renaming_a_company_onto_another_name_is_a_conflict() -> None:
    target = Company(company_id=uuid.uuid4(), tenant_id=_TENANT, name="Acme")
    other = Company(company_id=uuid.uuid4(), tenant_id=_TENANT, name="Globex")
    repo = CompanyRepository(_session(_result(scalar=target), _result(scalar=other)))

    with pytest.raises(ConflictError, match="already exists"):
        await repo.update(_TENANT, target.company_id, CompanyUpdate(name="Globex"))


@pytest.mark.asyncio
async def test_renaming_a_company_to_its_own_name_is_allowed() -> None:
    """Re-saving an unchanged name must not collide with the row being edited."""
    company = Company(company_id=uuid.uuid4(), tenant_id=_TENANT, name="Acme")
    repo = CompanyRepository(_session(_result(scalar=company), _result(scalar=company)))

    updated = await repo.update(_TENANT, company.company_id, CompanyUpdate(name="Acme Corp"))

    assert updated.name == "Acme Corp"


@pytest.mark.asyncio
async def test_editing_a_job_onto_another_jobs_url_is_a_conflict() -> None:
    job = _job()
    other = _job(url="https://example.com/jobs/2")
    repo = JobRepository(_session(_result(scalar=job), _result(scalar=other)))

    with pytest.raises(ConflictError, match="already exists"):
        await repo.update(_TENANT, job.job_id, JobUpdate(url=HttpUrl("https://example.com/jobs/2")))


@pytest.mark.asyncio
async def test_resaving_a_jobs_own_url_is_allowed() -> None:
    job = _job()
    repo = JobRepository(_session(_result(scalar=job), _result(scalar=job)))

    await repo.update(_TENANT, job.job_id, JobUpdate(url=HttpUrl("https://example.com/jobs/1")))

    assert job.url == "https://example.com/jobs/1"


# ── deleting a company must not leave dangling links ─────────────────────────


@pytest.mark.asyncio
async def test_deleting_a_company_unlinks_its_jobs() -> None:
    """company_id has no FK, so nothing but this code prevents a dangling id."""
    company = Company(company_id=uuid.uuid4(), tenant_id=_TENANT, name="Acme")
    session = _session(_result(scalar=company), _result(rowcount=3))
    repo = CompanyRepository(session)

    unlinked = await repo.delete(_TENANT, company.company_id)

    assert unlinked == 3
    session.delete.assert_awaited_once_with(company)
