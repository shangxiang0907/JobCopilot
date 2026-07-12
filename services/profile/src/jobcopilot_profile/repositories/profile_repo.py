import uuid
from typing import Any

from jobcopilot_shared.exceptions import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_profile.models.profile import Profile
from jobcopilot_profile.schemas.profile import CredentialsUpdate, ProfileUpsert


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user(self, user_id: uuid.UUID) -> Profile:
        stmt = select(Profile).where(Profile.user_id == user_id)
        result = await self._session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile is None:
            raise NotFoundError(f"Profile for user {user_id} not found")
        return profile

    async def get_by_user_or_none(self, user_id: uuid.UUID) -> Profile | None:
        stmt = select(Profile).where(Profile.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, user_id: uuid.UUID, data: ProfileUpsert) -> Profile:
        profile = await self.get_by_user_or_none(user_id)
        if profile is None:
            profile = Profile(user_id=user_id)
            self._session.add(profile)

        if data.personal_info is not None:
            profile.personal_info = data.personal_info.model_dump(exclude_none=True)
        if data.preferences is not None:
            profile.preferences = data.preferences.model_dump()

        await self._session.flush()
        await self._session.refresh(profile)
        return profile

    async def update_credentials(
        self,
        user_id: uuid.UUID,
        data: CredentialsUpdate,
        encrypt: Any,
    ) -> Profile:
        profile = await self.get_by_user_or_none(user_id)
        if profile is None:
            profile = Profile(user_id=user_id)
            self._session.add(profile)

        if data.llm_api_key is not None:
            profile.llm_api_key_enc = encrypt(data.llm_api_key) if data.llm_api_key else None

        await self._session.flush()
        await self._session.refresh(profile)
        return profile
