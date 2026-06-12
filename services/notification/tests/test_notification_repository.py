"""Integration tests: Notification service — CRUD against a real PostgreSQL database.

Schema is created by `alembic upgrade head` (run as a CI step before pytest).
"""

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from jobcopilot_notification.repositories.notification_repo import NotificationRepository
from jobcopilot_shared.db import build_engine, build_session_factory


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = build_engine(os.environ["DATABASE_URL"])
    yield engine
    await engine.dispose()


@pytest.mark.integration
async def test_notification_create_and_list(db_engine: AsyncEngine) -> None:
    factory = build_session_factory(db_engine)
    tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
    async with factory() as session:
        async with session.begin():
            n = await NotificationRepository(session).create(
                tenant_id=tenant_id,
                user_id=user_id,
                type="job_discovered",
                title="New Job Found",
                body="A matching job has been discovered.",
                channel="in_app",
            )
            assert n.status == "pending"

    async with factory() as session:
        async with session.begin():
            items, total = await NotificationRepository(session).list_for_user(
                tenant_id, user_id, channel="in_app"
            )
            assert total == 1
            assert items[0].title == "New Job Found"


@pytest.mark.integration
async def test_notification_mark_sent(db_engine: AsyncEngine) -> None:
    factory = build_session_factory(db_engine)
    tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
    async with factory() as session:
        async with session.begin():
            repo = NotificationRepository(session)
            n = await repo.create(
                tenant_id=tenant_id,
                user_id=user_id,
                type="reminder",
                title="Reminder",
                body="Don't forget to apply.",
                channel="email",
            )
            await repo.mark_sent(n)

    async with factory() as session:
        async with session.begin():
            items, _ = await NotificationRepository(session).list_for_user(
                tenant_id, user_id, channel="email"
            )
            assert items[0].status == "sent"


@pytest.mark.integration
async def test_notification_tenant_isolation(db_engine: AsyncEngine) -> None:
    factory = build_session_factory(db_engine)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    user_id = uuid.uuid4()
    async with factory() as session:
        async with session.begin():
            await NotificationRepository(session).create(
                tenant_id=tenant_a,
                user_id=user_id,
                type="custom",
                title="Tenant A Only",
                body=".",
                channel="in_app",
            )

    async with factory() as session:
        async with session.begin():
            _, total = await NotificationRepository(session).list_for_user(
                tenant_b, user_id, channel="in_app"
            )
            assert total == 0
