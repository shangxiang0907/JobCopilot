import uuid

from jobcopilot_shared.exceptions import NotFoundError, TenantIsolationError
from sqlalchemy import func as sqlfunc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_job.models.company import Company
from jobcopilot_job.schemas.company import CompanyCreate, CompanyUpdate


class CompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, tenant_id: uuid.UUID, data: CompanyCreate) -> Company:
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

        stmt = select(Company).where(
            Company.tenant_id == tenant_id,
            sqlfunc.lower(sqlfunc.btrim(Company.name)) == normalised.lower(),
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
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
    ) -> tuple[list[Company], int]:
        total_stmt = select(sqlfunc.count()).select_from(
            select(Company.company_id).where(Company.tenant_id == tenant_id).subquery()
        )
        total = (await self._session.execute(total_stmt)).scalar_one()

        rows_stmt = (
            select(Company)
            .where(Company.tenant_id == tenant_id)
            .order_by(Company.created_at.desc())
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
        patch = data.model_dump(exclude_none=True)
        if "website" in patch and patch["website"] is not None:
            patch["website"] = str(patch["website"])
        for field, value in patch.items():
            setattr(company, field, value)
        await self._session.flush()
        await self._session.refresh(company)
        return company

    async def delete(self, tenant_id: uuid.UUID, company_id: uuid.UUID) -> None:
        company = await self.get(tenant_id, company_id)
        await self._session.delete(company)
        await self._session.flush()

    async def _guard_tenant(self, company: Company, tenant_id: uuid.UUID) -> None:
        if company.tenant_id != tenant_id:
            raise TenantIsolationError("Company does not belong to tenant")
