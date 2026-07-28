import uuid
from typing import Any

from jobcopilot_shared.exceptions import NotFoundError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_profile.models.resume import Resume


class ResumeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: uuid.UUID,
        file_name: str,
        file_url: str,
        parsed_data: dict[str, Any] | None = None,
    ) -> Resume:
        version = await self._next_version(user_id)
        # Become the default when the user has none — a freshly uploaded first
        # resume was previously inert, so every AI action still failed the
        # no-resume-in-effect check until the user found the button. Later uploads
        # never steal the flag, so an explicit choice is never overridden.
        has_default = await self.get_default(user_id) is not None
        resume = Resume(
            user_id=user_id,
            file_name=file_name,
            file_url=file_url,
            parsed_data=parsed_data,
            version=version,
            is_default=not has_default,
        )
        self._session.add(resume)
        await self._session.flush()
        await self._session.refresh(resume)
        return resume

    async def get(self, user_id: uuid.UUID, resume_id: uuid.UUID) -> Resume:
        stmt = select(Resume).where(
            Resume.resume_id == resume_id,
            Resume.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        resume = result.scalar_one_or_none()
        if resume is None:
            raise NotFoundError(f"Resume {resume_id} not found")
        return resume

    async def list(self, user_id: uuid.UUID) -> list[Resume]:
        stmt = select(Resume).where(Resume.user_id == user_id).order_by(Resume.version.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_default(self, user_id: uuid.UUID) -> Resume | None:
        stmt = select(Resume).where(
            Resume.user_id == user_id,
            Resume.is_default.is_(True),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_default(self, user_id: uuid.UUID, resume_id: uuid.UUID) -> Resume:
        # Clear the flag across the user's resumes first — at most one default.
        clear_stmt = update(Resume).where(Resume.user_id == user_id).values(is_default=False)
        await self._session.execute(clear_stmt)

        resume = await self.get(user_id, resume_id)
        resume.is_default = True
        await self._session.flush()
        await self._session.refresh(resume)
        return resume

    async def update_metadata(
        self,
        user_id: uuid.UUID,
        resume_id: uuid.UUID,
        label: str | None,
        notes: str | None,
    ) -> Resume:
        """Edit label/notes. `None` leaves a field unchanged (see ResumeUpdate)."""
        resume = await self.get(user_id, resume_id)
        if label is not None:
            resume.label = label or None
        if notes is not None:
            resume.notes = notes or None
        await self._session.flush()
        await self._session.refresh(resume)
        return resume

    async def delete(self, user_id: uuid.UUID, resume_id: uuid.UUID) -> str:
        resume = await self.get(user_id, resume_id)
        file_url = resume.file_url
        await self._session.delete(resume)
        await self._session.flush()
        return file_url

    async def _next_version(self, user_id: uuid.UUID) -> int:
        from sqlalchemy import func as sqlfunc

        stmt = select(sqlfunc.max(Resume.version)).where(Resume.user_id == user_id)
        result = await self._session.execute(stmt)
        current_max = result.scalar_one_or_none()
        return (current_max or 0) + 1
