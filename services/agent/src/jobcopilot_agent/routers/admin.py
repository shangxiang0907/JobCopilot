"""Platform-admin AI usage overview (PRD v0.2 §3.10) — realm role `admin` only.

AI usage is proxied by job_analyses rows: every row is at least one
AnalyzerGraph run (the dominant LLM spend). Grouped per user, with a
current-calendar-month count for the monthly trend column.
"""

from datetime import UTC, datetime

from fastapi import APIRouter
from jobcopilot_shared.auth import AdminClaimsDep
from pydantic import BaseModel
from sqlalchemy import func, select

from jobcopilot_agent.deps import DbDep
from jobcopilot_agent.models.analysis import JobAnalysis

router = APIRouter(prefix="/v1/admin/usage", tags=["admin"])


class UserAiUsage(BaseModel):
    user_id: str
    total_analyses: int
    analyses_this_month: int
    last_activity: datetime | None


class AiUsageResponse(BaseModel):
    users: list[UserAiUsage]
    total_analyses: int


@router.get("/ai", response_model=AiUsageResponse)
async def admin_ai_usage(claims: AdminClaimsDep, session: DbDep) -> AiUsageResponse:
    month_start = datetime.now(tz=UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_case = func.count(JobAnalysis.id).filter(JobAnalysis.created_at >= month_start)
    result = await session.execute(
        select(
            JobAnalysis.user_id,
            func.count(JobAnalysis.id),
            month_case,
            func.max(JobAnalysis.updated_at),
        )
        .group_by(JobAnalysis.user_id)
        .order_by(func.count(JobAnalysis.id).desc())
        .limit(200)
    )
    rows = result.all()
    users = [
        UserAiUsage(
            user_id=str(user_id),
            total_analyses=total,
            analyses_this_month=this_month,
            last_activity=last,
        )
        for user_id, total, this_month, last in rows
    ]
    return AiUsageResponse(users=users, total_analyses=sum(u.total_analyses for u in users))
