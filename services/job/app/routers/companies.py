import uuid

from fastapi import APIRouter, status
from jobcopilot_shared.schemas.common import PaginatedResponse

from app.deps import SessionDep, TenantIdDep
from app.repositories.company_repo import CompanyRepository
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate

router = APIRouter(prefix="/v1/companies", tags=["companies"])


@router.get("", response_model=PaginatedResponse[CompanyResponse])
async def list_companies(
    session: SessionDep,
    tenant_id: TenantIdDep,
    page: int = 1,
    size: int = 20,
) -> PaginatedResponse[CompanyResponse]:
    repo = CompanyRepository(session)
    companies, total = await repo.get_all(tenant_id, page=page, size=size)
    items = [CompanyResponse.model_validate(c) for c in companies]
    return PaginatedResponse(
        items=items, total=total, page=page, size=size, has_next=(page * size < total)
    )


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    body: CompanyCreate,
    session: SessionDep,
    tenant_id: TenantIdDep,
) -> CompanyResponse:
    repo = CompanyRepository(session)
    company = await repo.create(tenant_id, body)
    return CompanyResponse.model_validate(company)


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: uuid.UUID,
    session: SessionDep,
    tenant_id: TenantIdDep,
) -> CompanyResponse:
    repo = CompanyRepository(session)
    company = await repo.get(tenant_id, company_id)
    return CompanyResponse.model_validate(company)


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: uuid.UUID,
    body: CompanyUpdate,
    session: SessionDep,
    tenant_id: TenantIdDep,
) -> CompanyResponse:
    repo = CompanyRepository(session)
    company = await repo.update(tenant_id, company_id, body)
    return CompanyResponse.model_validate(company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: uuid.UUID,
    session: SessionDep,
    tenant_id: TenantIdDep,
) -> None:
    repo = CompanyRepository(session)
    await repo.delete(tenant_id, company_id)
