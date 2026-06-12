import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_notification.models.notification import Notification, NotificationPreference


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        type: str,
        title: str,
        body: str,
        channel: str,
        metadata: dict | None = None,
    ) -> Notification:
        n = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            channel=channel,
            status="pending",
            metadata_=metadata or {},
        )
        self._s.add(n)
        await self._s.flush()
        return n

    async def mark_sent(self, notification: Notification) -> None:
        notification.status = "sent"
        await self._s.flush()

    async def mark_failed(self, notification: Notification, error: str) -> None:
        notification.status = "failed"
        notification.error_message = error
        await self._s.flush()

    async def mark_read(
        self, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> Notification | None:
        stmt = (
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=datetime.now(tz=UTC))
            .returning(Notification)
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        channel: str = "in_app",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Notification], int]:
        base = (
            select(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
                Notification.channel == channel,
            )
            .order_by(Notification.created_at.desc())
        )
        count_stmt = select(func.count()).select_from(base.subquery())
        total: int = (await self._s.execute(count_stmt)).scalar_one()

        page_stmt = base.offset((page - 1) * page_size).limit(page_size)
        items = list((await self._s.execute(page_stmt)).scalars().all())
        return items, total

    async def delete(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        n = await self._s.get(Notification, notification_id)
        if n is None or n.user_id != user_id:
            return False
        await self._s.delete(n)
        return True

    # --- Preferences ---

    async def get_preference(self, user_id: uuid.UUID) -> NotificationPreference | None:
        stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def upsert_preference(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        **kwargs: object,
    ) -> NotificationPreference:
        pref = await self.get_preference(user_id)
        if pref is None:
            pref = NotificationPreference(tenant_id=tenant_id, user_id=user_id)
            self._s.add(pref)
        for key, val in kwargs.items():
            if val is not None:
                setattr(pref, key, val)
        await self._s.flush()
        return pref
