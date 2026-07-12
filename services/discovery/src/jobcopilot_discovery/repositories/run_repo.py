import uuid
from datetime import UTC, datetime

from jobcopilot_shared.exceptions import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_discovery.models.discovery_run import DiscoveryRun


class RunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: uuid.UUID,
        config_id: uuid.UUID,
        temporal_run_id: str | None = None,
    ) -> DiscoveryRun:
        run = DiscoveryRun(
            user_id=user_id,
            config_id=config_id,
            temporal_run_id=temporal_run_id,
            status="pending",
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def get(self, user_id: uuid.UUID, run_id: uuid.UUID) -> DiscoveryRun:
        result = await self._session.execute(
            select(DiscoveryRun).where(
                DiscoveryRun.run_id == run_id,
                DiscoveryRun.user_id == user_id,
            )
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise NotFoundError(f"Discovery run {run_id} not found")
        return run

    async def get_by_id(self, run_id: uuid.UUID) -> DiscoveryRun:
        """Used internally by the Temporal worker (no user scoping needed)."""
        result = await self._session.execute(
            select(DiscoveryRun).where(DiscoveryRun.run_id == run_id)
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise NotFoundError(f"Discovery run {run_id} not found")
        return run

    async def list(self, user_id: uuid.UUID, limit: int = 20) -> list[DiscoveryRun]:
        result = await self._session.execute(
            select(DiscoveryRun)
            .where(DiscoveryRun.user_id == user_id)
            .order_by(DiscoveryRun.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        run_id: uuid.UUID,
        status: str,
        jobs_discovered: int = 0,
        error_message: str | None = None,
    ) -> DiscoveryRun:
        run = await self.get_by_id(run_id)
        run.status = status
        if jobs_discovered:
            run.jobs_discovered = jobs_discovered
        if error_message is not None:
            run.error_message = error_message
        if status in ("completed", "failed"):
            run.finished_at = datetime.now(tz=UTC)
        await self._session.flush()
        return run
