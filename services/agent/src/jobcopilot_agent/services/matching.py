"""
Resume match service — runs ResumeGraph for detailed gap analysis.
Owns its unit of work like the analysis/interview services, so it can be
reused by any caller (HTTP endpoint today, ReAct tool if one is added).
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from jobcopilot_shared.exceptions import ExternalServiceError, NoActiveResumeError
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_agent.config import settings
from jobcopilot_agent.graphs.resume_graph import ResumeState, resume_graph
from jobcopilot_agent.repositories.analysis_repo import AnalysisRepository

log = logging.getLogger(__name__)


@dataclass
class ResumeMatchOutcome:
    analysis_id: uuid.UUID
    match_score: float
    gap_analysis: dict[str, Any]
    suggestions: list[dict[str, Any]]


async def _fetch_resume_text(user_id: uuid.UUID) -> str:
    """Return the active resume text, "" when the user has none.

    A profile-service failure raises ExternalServiceError instead of being
    folded into "" — otherwise a transient outage would be misreported to the
    user as "no resume uploaded".
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.profile_service_url}/internal/profiles/{user_id}")
    except httpx.HTTPError as exc:
        log.warning("profile_fetch_failed", extra={"error": str(exc)})
        raise ExternalServiceError("Profile service is unavailable") from exc
    if resp.status_code == 200:
        return str(resp.json().get("active_resume_text") or "")
    if resp.status_code == 404:
        return ""
    log.warning("profile_fetch_failed", extra={"status_code": resp.status_code})
    raise ExternalServiceError("Profile service returned an unexpected response")


async def run_resume_match(
    session: AsyncSession,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> ResumeMatchOutcome | None:
    """Run ResumeGraph against the stored JD structure and persist the results.

    Returns None when no prior analysis exists for (job, user, tenant).
    Raises NoActiveResumeError before any LLM call when the user has no active
    resume, and ExternalServiceError when the profile service is unreachable.
    Commits the session on success.
    """
    repo = AnalysisRepository(session)
    analysis = await repo.get_by_job_user(job_id, user_id, tenant_id)
    if not analysis or not analysis.jd_structured:
        return None

    # Fail before the LLM call — an empty resume would only produce a
    # meaningless gap analysis at real token cost.
    resume_text = await _fetch_resume_text(user_id)
    if not resume_text.strip():
        raise NoActiveResumeError("Upload and activate a resume before running a match")

    state: ResumeState = {
        "job_id": str(job_id),
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "jd_structured": analysis.jd_structured,
        "resume_text": resume_text,
        "match_score": 0.0,
        "gap_analysis": {},
        "suggestions": [],
        "error": None,
    }
    result = await resume_graph.ainvoke(state)

    match_score = float(result.get("match_score", 0.0))
    gap_analysis = result.get("gap_analysis", {})
    suggestions = result.get("suggestions", [])
    await repo.update_analysis(
        analysis,
        match_score=match_score,
        resume_suggestions={"gap_analysis": gap_analysis, "suggestions": suggestions},
        status="done",
    )
    await session.commit()

    return ResumeMatchOutcome(
        analysis_id=analysis.id,
        match_score=match_score,
        gap_analysis=gap_analysis,
        suggestions=suggestions,
    )
