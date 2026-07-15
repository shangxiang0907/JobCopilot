"""
Dispatcher: creates Notification DB rows and dispatches to each requested channel.
Called by the RabbitMQ consumer and the /internal/notify endpoint.
"""

import logging
import uuid
from typing import Any

from jobcopilot_shared.db import build_engine, build_session_factory
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_notification.config import settings
from jobcopilot_notification.models.notification import Notification
from jobcopilot_notification.repositories.notification_repo import NotificationRepository
from jobcopilot_notification.services.channels.email import send_email

log = logging.getLogger(__name__)


async def dispatch(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: str,
    channels: list[str],
    metadata: dict[str, Any] | None = None,
) -> list[Notification]:
    repo = NotificationRepository(session)
    pref = await repo.get_preference(user_id)
    created: list[Notification] = []

    for channel in channels:
        n = await repo.create(
            tenant_id=tenant_id,
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            channel=channel,
            metadata=metadata or {},
        )
        created.append(n)

        try:
            if channel == "in_app":
                # Stored in DB — no external call needed
                await repo.mark_sent(n)

            elif channel == "email":
                if pref and pref.email_enabled and pref.email_address:
                    await send_email(to_address=pref.email_address, subject=title, body=body)
                    await repo.mark_sent(n)
                else:
                    await repo.mark_failed(n, "email_not_configured")

            else:
                await repo.mark_failed(n, f"unknown_channel:{channel}")

        except Exception as exc:
            log.error(
                "dispatch_channel_failed",
                extra={"channel": channel, "user_id": str(user_id), "error": str(exc)},
            )
            await repo.mark_failed(n, str(exc))

    return created


async def dispatch_standalone(
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: str,
    channels: list[str],
    metadata: dict[str, Any] | None = None,
) -> None:
    """Convenience wrapper that creates its own DB session — used by the MQ consumer."""
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    try:
        async with session_factory() as session:
            async with session.begin():
                await dispatch(
                    session,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    type=type,
                    title=title,
                    body=body,
                    channels=channels,
                    metadata=metadata,
                )
    finally:
        await engine.dispose()
