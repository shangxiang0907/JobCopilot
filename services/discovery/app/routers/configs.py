import uuid

from fastapi import APIRouter, status

from app.deps import SessionDep, UserIdDep
from app.repositories.config_repo import ConfigRepository
from app.schemas.discovery import (
    DiscoveryConfigCreate,
    DiscoveryConfigResponse,
    DiscoveryConfigUpdate,
)

router = APIRouter(prefix="/v1/discovery/configs", tags=["discovery-configs"])


@router.get("", response_model=list[DiscoveryConfigResponse])
async def list_configs(session: SessionDep, user_id: UserIdDep) -> list[DiscoveryConfigResponse]:
    repo = ConfigRepository(session)
    configs = await repo.list(user_id)
    return [DiscoveryConfigResponse.model_validate(c) for c in configs]


@router.post("", response_model=DiscoveryConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    body: DiscoveryConfigCreate,
    session: SessionDep,
    user_id: UserIdDep,
) -> DiscoveryConfigResponse:
    repo = ConfigRepository(session)
    config = await repo.create(user_id, body)
    return DiscoveryConfigResponse.model_validate(config)


@router.get("/{config_id}", response_model=DiscoveryConfigResponse)
async def get_config(
    config_id: uuid.UUID,
    session: SessionDep,
    user_id: UserIdDep,
) -> DiscoveryConfigResponse:
    repo = ConfigRepository(session)
    config = await repo.get(user_id, config_id)
    return DiscoveryConfigResponse.model_validate(config)


@router.patch("/{config_id}", response_model=DiscoveryConfigResponse)
async def update_config(
    config_id: uuid.UUID,
    body: DiscoveryConfigUpdate,
    session: SessionDep,
    user_id: UserIdDep,
) -> DiscoveryConfigResponse:
    repo = ConfigRepository(session)
    config = await repo.update(user_id, config_id, body)
    return DiscoveryConfigResponse.model_validate(config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: uuid.UUID,
    session: SessionDep,
    user_id: UserIdDep,
) -> None:
    repo = ConfigRepository(session)
    await repo.delete(user_id, config_id)
