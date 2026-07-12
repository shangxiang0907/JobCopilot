import uuid

from jobcopilot_shared.exceptions import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_discovery.models.discovery_config import DiscoveryConfig
from jobcopilot_discovery.schemas.discovery import DiscoveryConfigCreate, DiscoveryConfigUpdate


class ConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: uuid.UUID, body: DiscoveryConfigCreate) -> DiscoveryConfig:
        config = DiscoveryConfig(
            user_id=user_id,
            keywords=body.keywords,
            locations=body.locations,
            job_types=body.job_types,
            company_boards=body.company_boards,
            salary_min=body.salary_min,
            is_active=body.is_active,
            schedule_cron=body.schedule_cron,
        )
        self._session.add(config)
        await self._session.flush()
        return config

    async def get(self, user_id: uuid.UUID, config_id: uuid.UUID) -> DiscoveryConfig:
        result = await self._session.execute(
            select(DiscoveryConfig).where(
                DiscoveryConfig.config_id == config_id,
                DiscoveryConfig.user_id == user_id,
            )
        )
        config = result.scalar_one_or_none()
        if config is None:
            raise NotFoundError(f"Discovery config {config_id} not found")
        return config

    async def list(self, user_id: uuid.UUID) -> list[DiscoveryConfig]:
        result = await self._session.execute(
            select(DiscoveryConfig).where(DiscoveryConfig.user_id == user_id)
        )
        return list(result.scalars().all())

    async def update(
        self, user_id: uuid.UUID, config_id: uuid.UUID, body: DiscoveryConfigUpdate
    ) -> DiscoveryConfig:
        config = await self.get(user_id, config_id)
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(config, field, value)
        await self._session.flush()
        return config

    async def delete(self, user_id: uuid.UUID, config_id: uuid.UUID) -> None:
        config = await self.get(user_id, config_id)
        await self._session.delete(config)
        await self._session.flush()
