import uuid

from fastapi import APIRouter, status
from jobcopilot_shared.schemas.common import PaginatedResponse

from jobcopilot_discovery.deps import SessionDep, UserIdDep
from jobcopilot_discovery.repositories.config_repo import ConfigRepository
from jobcopilot_discovery.schemas.discovery import (
    DiscoveryConfigCreate,
    DiscoveryConfigResponse,
    DiscoveryConfigUpdate,
)

router = APIRouter(prefix="/v1/discovery/configs", tags=["discovery-configs"])


@router.get("", response_model=PaginatedResponse[DiscoveryConfigResponse])
async def list_configs(
    session: SessionDep, user_id: UserIdDep
) -> PaginatedResponse[DiscoveryConfigResponse]:
    """All /v1 collection endpoints return PaginatedResponse — see CLAUDE.md."""
    repo = ConfigRepository(session)
    configs = await repo.list(user_id)
    items = [DiscoveryConfigResponse.model_validate(c) for c in configs]
    return PaginatedResponse(
        items=items, total=len(items), page=1, size=max(len(items), 1), has_next=False
    )


@router.post("", response_model=DiscoveryConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    body: DiscoveryConfigCreate,
    session: SessionDep,
    user_id: UserIdDep,
) -> DiscoveryConfigResponse:
    repo = ConfigRepository(session)
    config = await repo.create(user_id, body)
    await session.commit()
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
    await session.commit()
    return DiscoveryConfigResponse.model_validate(config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: uuid.UUID,
    session: SessionDep,
    user_id: UserIdDep,
) -> None:
    repo = ConfigRepository(session)
    await repo.delete(user_id, config_id)
    await session.commit()
