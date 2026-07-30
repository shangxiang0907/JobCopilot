"""
Interview preparation service — shared by the /v1/agent/interview endpoint and
the prepare_interview ReAct tool. Both run in the same process as
InterviewGraph, so the graph is invoked directly (no HTTP self-call).
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from jobcopilot_shared.exceptions import ExternalServiceError
from jobcopilot_shared.metrics import record_degradation
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_agent.graphs.interview_graph import InterviewState, interview_graph
from jobcopilot_agent.repositories.analysis_repo import AnalysisRepository

log = logging.getLogger(__name__)


@dataclass
class InterviewPreparation:
    analysis_id: uuid.UUID
    behavioral_questions: list[dict[str, Any]]
    technical_questions: list[dict[str, Any]]


async def prepare_interview_questions(
    session: AsyncSession,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> InterviewPreparation | None:
    """Run InterviewGraph for a job and persist the generated questions.

    Returns None when no prior analysis exists for (job, user, tenant);
    the caller decides how to surface that (404 vs. tool error message).
    Commits the session on success.
    """
    repo = AnalysisRepository(session)
    analysis = await repo.get_by_job_user(job_id, user_id, tenant_id)
    if not analysis or not analysis.jd_structured:
        return None

    state: InterviewState = {
        "job_id": str(job_id),
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "jd_structured": analysis.jd_structured,
        "behavioral_questions": [],
        "technical_questions": [],
        "behavioral_error": None,
        "technical_error": None,
    }
    result = await interview_graph.ainvoke(state)

    behavioral = result.get("behavioral_questions", [])
    technical = result.get("technical_questions", [])
    behavioral_error = result.get("behavioral_error")
    technical_error = result.get("technical_error")

    if behavioral_error and technical_error:
        # Nothing was generated. Persisting two empty lists as status="done"
        # told the user "your interview prep is ready: 0 questions" and hid an
        # LLM outage completely — the stored preparation stays untouched now.
        log.warning(
            "interview_prep_failed",
            extra={"behavioral_error": behavioral_error, "technical_error": technical_error},
        )
        raise ExternalServiceError("Could not generate interview questions right now")

    if behavioral_error or technical_error:
        # Half the preparation is still worth having, so this one degrades on
        # purpose — but it is counted, not swallowed: a rising
        # jobcopilot_degraded_operations_total{operation="interview_prep"} is
        # how a half-broken prompt or a flaky model surfaces in production.
        missing = "behavioral" if behavioral_error else "technical"
        log.warning(
            "interview_prep_partial",
            extra={"missing": missing, "error": behavioral_error or technical_error},
        )
        record_degradation(operation="interview_prep", reason=f"{missing}_llm_failed")
    # The earlier SELECT autobegan a transaction on this session, so an
    # explicit session.begin() here would raise InvalidRequestError —
    # mutate and commit on the already-open transaction instead.
    await repo.update_analysis(
        analysis,
        interview_questions={"behavioral": behavioral, "technical": technical},
        status="done",
    )
    await session.commit()

    return InterviewPreparation(
        analysis_id=analysis.id,
        behavioral_questions=behavioral,
        technical_questions=technical,
    )
