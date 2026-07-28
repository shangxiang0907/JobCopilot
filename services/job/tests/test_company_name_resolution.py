"""Company-name resolution is an idempotent upsert, not a duplicate factory.

Jobs arrive from every path (manual entry, JD import, discovery) carrying a
free-text company_name. Resolving that name to a companies row is what makes the
/companies library populate at all — and without normalisation it would fill
with "Acme", "acme " and "ACME" as three separate companies each owning a slice
of the user's jobs. Matching here must agree with the uq_companies_tenant_name
index in migration 0004; if they ever disagree the upsert starts raising
IntegrityError instead of finding the existing row.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jobcopilot_job.models.company import Company
from jobcopilot_job.repositories.company_repo import CompanyRepository
from jobcopilot_job.repositories.job_repo import JobRepository

_TENANT = uuid.uuid4()


def _repo(found: Company | None = None) -> tuple[CompanyRepository, AsyncMock]:
    """Repository plus its mock session, so assertions never reach into `_session`."""
    result = AsyncMock()
    result.scalar_one_or_none = MagicMock(return_value=found)
    session = AsyncMock()
    session.add = MagicMock()  # Session.add is sync — AsyncMock would leave a coroutine unawaited
    session.execute = AsyncMock(return_value=result)
    return CompanyRepository(session), session


def _existing(name: str) -> Company:
    return Company(company_id=uuid.uuid4(), tenant_id=_TENANT, name=name)


@pytest.mark.asyncio
@pytest.mark.parametrize("incoming", ["Acme", "acme", "ACME", "  Acme  ", "acme "])
async def test_name_variants_resolve_to_the_same_row(incoming: str) -> None:
    """Case and surrounding whitespace must never mint a second company."""
    existing = _existing("Acme")
    repo, session = _repo(found=existing)

    company = await repo.resolve_by_name(_TENANT, incoming)

    assert company is not None
    assert company.company_id == existing.company_id
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_name_creates_one_row_keeping_the_users_capitalisation() -> None:
    repo, session = _repo(found=None)

    company = await repo.resolve_by_name(_TENANT, "  Stripe  ")

    assert company is not None
    assert company.name == "Stripe"  # trimmed for storage, not lower-cased
    assert company.tenant_id == _TENANT
    session.add.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("blank", ["", "   "])
async def test_blank_name_yields_no_company_rather_than_an_empty_one(blank: str) -> None:
    """A job with no company is legitimate; a company named "" never is."""
    repo, session = _repo()
    company = await repo.resolve_by_name(_TENANT, blank)

    assert company is None
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_explicit_company_id_wins_over_the_name() -> None:
    """The caller picked a specific row; re-deriving it could move the job."""
    session = AsyncMock()
    session.add = MagicMock()
    repo = JobRepository(session)
    chosen = uuid.uuid4()

    with patch.object(CompanyRepository, "resolve_by_name", new_callable=AsyncMock) as resolve:
        company_id = await repo._resolve_company_id(_TENANT, "Acme", chosen)

    assert company_id == chosen
    resolve.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_company_id_falls_back_to_name_resolution() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    repo = JobRepository(session)
    resolved = _existing("Acme")

    with patch.object(
        CompanyRepository, "resolve_by_name", new_callable=AsyncMock, return_value=resolved
    ):
        company_id = await repo._resolve_company_id(_TENANT, "Acme", None)

    assert company_id == resolved.company_id
