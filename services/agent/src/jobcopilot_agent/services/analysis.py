"""
Job analysis service — shared by the /v1/agent/analyze endpoint and the
analyze_job ReAct tool. Both run in the same process as AnalyzerGraph,
so the graph is invoked directly (no HTTP self-call).
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_agent.graphs.analyzer_graph import AnalyzerState, analyzer_graph
from jobcopilot_agent.repositories.analysis_repo import AnalysisRepository


@dataclass
class JobAnalysisOutcome:
    analysis_id: uuid.UUID
    jd_structured: dict[str, Any]
    skills_required: list[str]
    match_score: float
    status: str


async def run_job_analysis(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    url: str,
    title: str,
    company_name: str,
    location: str,
    raw_text: str,
) -> JobAnalysisOutcome:
    """Run AnalyzerGraph and persist the structured analysis. Commits on success."""
    state: AnalyzerState = {
        "job_id": str(job_id),
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "url": url,
        "title": title,
        "company_name": company_name,
        "location": location,
        "raw_text": raw_text,
        "resume_text": "",
        "jd_structured": {},
        "skills_required": [],
        "match_score": 0.0,
        "error": None,
    }
    result = await analyzer_graph.ainvoke(state)

    repo = AnalysisRepository(session)
    analysis = await repo.get_or_create(job_id, user_id, tenant_id)
    await repo.update_analysis(
        analysis,
        jd_structured=result.get("jd_structured"),
        skills_required=result.get("skills_required"),
        match_score=result.get("match_score"),
        status="done" if not result.get("error") else "error",
        error_message=result.get("error"),
    )
    await session.commit()

    return JobAnalysisOutcome(
        analysis_id=analysis.id,
        jd_structured=result.get("jd_structured", {}),
        skills_required=result.get("skills_required", []),
        match_score=result.get("match_score", 0.0),
        status=analysis.status,
    )
