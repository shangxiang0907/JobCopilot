import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import JobAnalysis


class AnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, analysis: JobAnalysis) -> JobAnalysis:
        self._session.add(analysis)
        await self._session.flush()
        return analysis

    async def get_by_job_user(
        self, job_id: uuid.UUID, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> JobAnalysis | None:
        result = await self._session.execute(
            select(JobAnalysis).where(
                JobAnalysis.job_id == job_id,
                JobAnalysis.user_id == user_id,
                JobAnalysis.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self, job_id: uuid.UUID, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> JobAnalysis:
        existing = await self.get_by_job_user(job_id, user_id, tenant_id)
        if existing:
            return existing
        analysis = JobAnalysis(
            job_id=job_id,
            user_id=user_id,
            tenant_id=tenant_id,
            status="pending",
        )
        return await self.create(analysis)

    async def update_analysis(
        self,
        analysis: JobAnalysis,
        *,
        jd_structured: dict | None = None,
        skills_required: list | None = None,
        match_score: float | None = None,
        resume_suggestions: dict | None = None,
        interview_questions: dict | None = None,
        status: str | None = None,
        error_message: str | None = None,
    ) -> JobAnalysis:
        if jd_structured is not None:
            analysis.jd_structured = jd_structured
        if skills_required is not None:
            analysis.skills_required = skills_required
        if match_score is not None:
            analysis.match_score = match_score
        if resume_suggestions is not None:
            analysis.resume_suggestions = resume_suggestions
        if interview_questions is not None:
            analysis.interview_questions = interview_questions
        if status is not None:
            analysis.status = status
        if error_message is not None:
            analysis.error_message = error_message
        await self._session.flush()
        return analysis

    async def list_by_user(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Sequence[JobAnalysis]:
        result = await self._session.execute(
            select(JobAnalysis).where(
                JobAnalysis.user_id == user_id,
                JobAnalysis.tenant_id == tenant_id,
            )
        )
        return result.scalars().all()
