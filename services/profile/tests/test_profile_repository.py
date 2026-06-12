"""Integration tests: Profile service — CRUD against a real PostgreSQL database.

Schema is created by `alembic upgrade head` (run as a CI step before pytest).
"""

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
from jobcopilot_profile.repositories.profile_repo import ProfileRepository
from jobcopilot_profile.schemas.profile import PersonalInfo, ProfileUpsert
from jobcopilot_shared.db import build_engine, build_session_factory
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = build_engine(os.environ["DATABASE_URL"])
    yield engine
    await engine.dispose()


@pytest.mark.integration
async def test_profile_upsert_and_get(db_engine: AsyncEngine) -> None:
    factory = build_session_factory(db_engine)
    user_id = uuid.uuid4()
    async with factory() as session:
        async with session.begin():
            profile = await ProfileRepository(session).upsert(
                user_id,
                ProfileUpsert(
                    personal_info=PersonalInfo(name="Test User", email="test@example.com")
                ),
            )
            assert profile.user_id == user_id
            assert profile.personal_info is not None
            assert profile.personal_info["name"] == "Test User"

    async with factory() as session:
        async with session.begin():
            fetched = await ProfileRepository(session).get_by_user(user_id)
            assert fetched.personal_info is not None
            assert fetched.personal_info["email"] == "test@example.com"


@pytest.mark.integration
async def test_profile_upsert_idempotent(db_engine: AsyncEngine) -> None:
    factory = build_session_factory(db_engine)
    user_id = uuid.uuid4()
    async with factory() as session:
        async with session.begin():
            await ProfileRepository(session).upsert(
                user_id, ProfileUpsert(personal_info=PersonalInfo(name="First"))
            )

    async with factory() as session:
        async with session.begin():
            updated = await ProfileRepository(session).upsert(
                user_id, ProfileUpsert(personal_info=PersonalInfo(name="Updated"))
            )
            assert updated.personal_info is not None
            assert updated.personal_info["name"] == "Updated"

    async with factory() as session:
        async with session.begin():
            result = await ProfileRepository(session).get_by_user_or_none(user_id)
            assert result is not None
            assert result.personal_info is not None
            assert result.personal_info["name"] == "Updated"
