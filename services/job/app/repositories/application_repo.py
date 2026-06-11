import uuid
from datetime import UTC, datetime

from jobcopilot_shared.exceptions import NotFoundError, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import VALID_TRANSITIONS, Application
from app.models.application_event import ApplicationEvent
from app.schemas.application import (
    ApplicationCreate,
    ApplicationStatusUpdate,
    ApplicationUpdate,
    InternalAnalysisUpdate,
)


class ApplicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: uuid.UUID, data: ApplicationCreate) -> Application:
        app = Application(
            user_id=user_id,
            job_id=data.job_id,
            notes=data.notes,
            status="discovered",
        )
        self._session.add(app)
        await self._session.flush()
        await self._session.refresh(app)
        return app

    async def get(self, user_id: uuid.UUID, application_id: uuid.UUID) -> Application:
        stmt = select(Application).where(
            Application.application_id == application_id,
            Application.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        app = result.scalar_one_or_none()
        if app is None:
            raise NotFoundError(f"Application {application_id} not found")
        return app

    async def get_internal(self, application_id: uuid.UUID) -> Application:
        stmt = select(Application).where(Application.application_id == application_id)
        result = await self._session.execute(stmt)
        app = result.scalar_one_or_none()
        if app is None:
            raise NotFoundError(f"Application {application_id} not found")
        return app

    async def get_all(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        size: int = 20,
        status: str | None = None,
    ) -> tuple[list[Application], int]:
        from sqlalchemy import func as sqlfunc

        filters = [Application.user_id == user_id]
        if status:
            filters.append(Application.status == status)

        total_stmt = select(sqlfunc.count()).select_from(
            select(Application.application_id).where(*filters).subquery()
        )
        total = (await self._session.execute(total_stmt)).scalar_one()

        rows_stmt = (
            select(Application)
            .where(*filters)
            .order_by(Application.updated_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = list((await self._session.execute(rows_stmt)).scalars().all())
        return rows, total

    async def transition_status(
        self,
        user_id: uuid.UUID,
        application_id: uuid.UUID,
        data: ApplicationStatusUpdate,
    ) -> Application:
        app = await self.get(user_id, application_id)
        from_status = app.status
        to_status = data.status

        allowed = VALID_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise ValidationError(
                f"Cannot transition from '{from_status}' to '{to_status}'. "
                f"Allowed: {sorted(allowed) or 'none (terminal state)'}"
            )

        app.status = to_status
        if to_status == "applied":
            app.applied_at = datetime.now(UTC)

        event = ApplicationEvent(
            application_id=application_id,
            from_status=from_status,
            to_status=to_status,
            note=data.note,
        )
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(app)
        return app

    async def update_notes(
        self,
        user_id: uuid.UUID,
        application_id: uuid.UUID,
        data: ApplicationUpdate,
    ) -> Application:
        app = await self.get(user_id, application_id)
        if data.notes is not None:
            app.notes = data.notes
        await self._session.flush()
        await self._session.refresh(app)
        return app

    async def update_analysis(
        self, application_id: uuid.UUID, data: InternalAnalysisUpdate
    ) -> Application:
        app = await self.get_internal(application_id)
        if data.match_score is not None:
            app.match_score = data.match_score
        if data.resume_suggestions is not None:
            app.resume_suggestions = data.resume_suggestions
        await self._session.flush()
        await self._session.refresh(app)
        return app

    async def get_events(
        self, user_id: uuid.UUID, application_id: uuid.UUID
    ) -> list[ApplicationEvent]:
        await self.get(user_id, application_id)  # ownership check
        stmt = (
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == application_id)
            .order_by(ApplicationEvent.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, user_id: uuid.UUID, application_id: uuid.UUID) -> None:
        app = await self.get(user_id, application_id)
        await self._session.delete(app)
        await self._session.flush()
