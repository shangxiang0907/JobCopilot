"""Unit tests for the shared job analysis service — graph and DB mocked."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jobcopilot_agent.services.analysis import run_job_analysis

_JOB_ID = uuid.uuid4()
_USER_ID = uuid.uuid4()
_TENANT_ID = uuid.uuid4()


@pytest.mark.asyncio
async def test_runs_graph_persists_and_commits() -> None:
    analysis = MagicMock()
    analysis.id = uuid.uuid4()
    analysis.status = "done"

    session = AsyncMock()
    repo = MagicMock()
    repo.get_or_create = AsyncMock(return_value=analysis)
    repo.update_analysis = AsyncMock()

    graph_result = {
        "jd_structured": {"title": "Python Engineer", "skills_required": ["Python"]},
        "skills_required": ["Python"],
        "match_score": 82.0,
        "error": None,
    }

    with (
        patch("jobcopilot_agent.services.analysis.AnalysisRepository", return_value=repo),
        patch("jobcopilot_agent.services.analysis.analyzer_graph") as mock_graph,
    ):
        mock_graph.ainvoke = AsyncMock(return_value=graph_result)
        outcome = await run_job_analysis(
            session,
            job_id=_JOB_ID,
            user_id=_USER_ID,
            tenant_id=_TENANT_ID,
            url="https://linkedin.com/jobs/1",
            title="Python Engineer",
            company_name="Acme",
            location="Remote",
            raw_text="We are hiring...",
        )

    assert outcome.analysis_id == analysis.id
    assert outcome.match_score == 82.0
    assert outcome.skills_required == ["Python"]
    assert outcome.status == "done"

    repo.update_analysis.assert_awaited_once_with(
        analysis,
        jd_structured=graph_result["jd_structured"],
        skills_required=["Python"],
        match_score=82.0,
        status="done",
        error_message=None,
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_graph_error_marks_analysis_as_error() -> None:
    analysis = MagicMock()
    analysis.id = uuid.uuid4()
    analysis.status = "error"

    session = AsyncMock()
    repo = MagicMock()
    repo.get_or_create = AsyncMock(return_value=analysis)
    repo.update_analysis = AsyncMock()

    with (
        patch("jobcopilot_agent.services.analysis.AnalysisRepository", return_value=repo),
        patch("jobcopilot_agent.services.analysis.analyzer_graph") as mock_graph,
    ):
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "jd_structured": {},
                "skills_required": [],
                "match_score": 0.0,
                "error": "LLM timeout",
            }
        )
        outcome = await run_job_analysis(
            session,
            job_id=_JOB_ID,
            user_id=_USER_ID,
            tenant_id=_TENANT_ID,
            url="",
            title="",
            company_name="",
            location="",
            raw_text="text",
        )

    assert outcome.status == "error"
    kwargs = repo.update_analysis.await_args.kwargs
    assert kwargs["status"] == "error"
    assert kwargs["error_message"] == "LLM timeout"
    session.commit.assert_awaited_once()


def test_analysis_response_validates_orm_object_with_id_attribute() -> None:
    """Regression: the ORM attr is `id` (UUIDPrimaryKeyMixin) but the wire field
    is `analysis_id` — model_validate used to raise, 500ing GET /analyses."""
    from datetime import UTC, datetime

    from jobcopilot_agent.models.analysis import JobAnalysis
    from jobcopilot_agent.schemas.agent import AnalysisResponse

    analysis = JobAnalysis(
        job_id=uuid.uuid4(), user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), status="done"
    )
    analysis.id = uuid.uuid4()
    analysis.created_at = datetime.now(UTC)
    analysis.updated_at = datetime.now(UTC)

    resp = AnalysisResponse.model_validate(analysis)
    assert resp.analysis_id == analysis.id
    assert resp.model_dump()["analysis_id"] == analysis.id
