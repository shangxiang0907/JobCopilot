import uuid
from typing import Any, cast

from jobcopilot_shared.exceptions import ConflictError, NotFoundError, TenantIsolationError
from jobcopilot_shared.logging import get_logger
from sqlalchemy import CursorResult, select, update
from sqlalchemy import func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_job.models.company import Company
from jobcopilot_job.models.job import Job
from jobcopilot_job.schemas.company import CompanyCreate, CompanyUpdate

logger = get_logger(__name__)


class CompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, tenant_id: uuid.UUID, data: CompanyCreate) -> Company:
        # uq_companies_tenant_name would reject this anyway, but as an
        # IntegrityError surfacing to the user as an opaque 500. A duplicate
        # name is an ordinary thing to type, so it gets an ordinary 409.
        if await self._find_by_name(tenant_id, data.name) is not None:
            raise ConflictError(f"A company named {data.name!r} already exists")
        company = Company(
            tenant_id=tenant_id,
            name=data.name,
            industry=data.industry,
            size=data.size,
            website=str(data.website) if data.website else None,
            notes=data.notes,
            is_blacklisted=data.is_blacklisted,
        )
        self._session.add(company)
        await self._session.flush()
        await self._session.refresh(company)
        return company

    async def _find_by_name(self, tenant_id: uuid.UUID, name: str) -> Company | None:
        """Look up by the same normalisation uq_companies_tenant_name uses."""
        normalised = name.strip()
        if not normalised:
            return None
        stmt = select(Company).where(
            Company.tenant_id == tenant_id,
            sqlfunc.lower(sqlfunc.btrim(Company.name)) == normalised.lower(),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def resolve_by_name(self, tenant_id: uuid.UUID, name: str) -> Company | None:
        """Find-or-create the tenant's company row for a free-text name.

        Job creation, editing and import all carry a company_name string rather
        than an id. Matching is case- and whitespace-insensitive to agree with
        the uq_companies_tenant_name index, so repeated imports of "Acme ",
        "acme" and "Acme" converge on one row instead of three.

        Returns None for a blank name — a job with no company is a legitimate
        state, and inventing a company row named "" would be worse than leaving
        company_id NULL.
        """
        normalised = name.strip()
        if not normalised:
            return None

        existing = await self._find_by_name(tenant_id, normalised)
        if existing is not None:
            return existing

        company = Company(tenant_id=tenant_id, name=normalised)
        self._session.add(company)
        await self._session.flush()
        await self._session.refresh(company)
        return company

    async def get(self, tenant_id: uuid.UUID, company_id: uuid.UUID) -> Company:
        stmt = select(Company).where(
            Company.company_id == company_id,
            Company.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        company = result.scalar_one_or_none()
        if company is None:
            raise NotFoundError(f"Company {company_id} not found")
        return company

    async def get_all(
        self,
        tenant_id: uuid.UUID,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
    ) -> tuple[list[Company], int]:
        filters = [Company.tenant_id == tenant_id]
        if search:
            filters.append(Company.name.ilike(f"%{search}%"))

        total_stmt = select(sqlfunc.count()).select_from(
            select(Company.company_id).where(*filters).subquery()
        )
        total = (await self._session.execute(total_stmt)).scalar_one()

        # A company library is browsed alphabetically, not by when the row
        # happened to be created — most rows are auto-created by job import and
        # their creation order carries no meaning for the user.
        rows_stmt = (
            select(Company)
            .where(*filters)
            .order_by(sqlfunc.lower(Company.name))
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = list((await self._session.execute(rows_stmt)).scalars().all())
        return rows, total

    async def update(
        self,
        tenant_id: uuid.UUID,
        company_id: uuid.UUID,
        data: CompanyUpdate,
    ) -> Company:
        company = await self.get(tenant_id, company_id)
        # exclude_unset, not exclude_none: an omitted field means "leave alone"
        # and an explicit null means "clear this" (see CompanyUpdate).
        patch = data.model_dump(exclude_unset=True)
        if patch.get("website") is not None:
            patch["website"] = str(patch["website"])
        if patch.get("name") is not None:
            clash = await self._find_by_name(tenant_id, patch["name"])
            if clash is not None and clash.company_id != company_id:
                raise ConflictError(f"A company named {patch['name']!r} already exists")
        for field, value in patch.items():
            setattr(company, field, value)
        await self._session.flush()
        await self._session.refresh(company)
        return company

    async def delete(self, tenant_id: uuid.UUID, company_id: uuid.UUID) -> int:
        """Delete the company and unlink its jobs. Returns how many were unlinked.

        company_id carries no foreign key, so nothing at the database level stops
        a deleted company from leaving jobs pointing at an id that resolves to
        nothing — a dangling link the company page would render as a silently
        broken reference. The jobs keep their company_name string, so no
        information is lost; only the link goes.
        """
        company = await self.get(tenant_id, company_id)
        # cast: session.execute() is typed Result[Any]; a DML statement always
        # yields a CursorResult, which is what carries rowcount.
        result = cast(
            "CursorResult[Any]",
            await self._session.execute(
                update(Job)
                .where(Job.tenant_id == tenant_id, Job.company_id == company_id)
                .values(company_id=None)
            ),
        )
        unlinked: int = result.rowcount
        await self._session.delete(company)
        await self._session.flush()
        if unlinked:
            logger.info(
                "company_deleted_jobs_unlinked",
                company_id=str(company_id),
                tenant_id=str(tenant_id),
                unlinked_jobs=unlinked,
            )
        return unlinked

    async def _guard_tenant(self, company: Company, tenant_id: uuid.UUID) -> None:
        if company.tenant_id != tenant_id:
            raise TenantIsolationError("Company does not belong to tenant")
