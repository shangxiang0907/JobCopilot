"""Platform-admin crawl usage overview (PRD v0.2 §3.10) — realm role `admin` only."""

from datetime import UTC, datetime

from fastapi import APIRouter
from jobcopilot_shared.auth import AdminClaimsDep
from pydantic import BaseModel
from sqlalchemy import func, select

from jobcopilot_discovery.deps import SessionDep
from jobcopilot_discovery.models.discovery_run import DiscoveryRun

router = APIRouter(prefix="/v1/admin/usage", tags=["admin"])


class UserCrawlUsage(BaseModel):
    user_id: str
    total_runs: int
    runs_this_month: int
    jobs_discovered: int
    last_run: datetime | None


class CrawlUsageResponse(BaseModel):
    users: list[UserCrawlUsage]
    total_runs: int


@router.get("/crawls", response_model=CrawlUsageResponse)
async def admin_crawl_usage(claims: AdminClaimsDep, session: SessionDep) -> CrawlUsageResponse:
    month_start = datetime.now(tz=UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_case = func.count(DiscoveryRun.run_id).filter(DiscoveryRun.started_at >= month_start)
    result = await session.execute(
        select(
            DiscoveryRun.user_id,
            func.count(DiscoveryRun.run_id),
            month_case,
            func.coalesce(func.sum(DiscoveryRun.jobs_discovered), 0),
            func.max(DiscoveryRun.started_at),
        )
        .group_by(DiscoveryRun.user_id)
        .order_by(func.count(DiscoveryRun.run_id).desc())
        .limit(200)
    )
    users = [
        UserCrawlUsage(
            user_id=str(user_id),
            total_runs=total,
            runs_this_month=this_month,
            jobs_discovered=jobs,
            last_run=last,
        )
        for user_id, total, this_month, jobs, last in result.all()
    ]
    return CrawlUsageResponse(users=users, total_runs=sum(u.total_runs for u in users))
