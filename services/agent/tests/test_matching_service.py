"""Unit tests for the resume match service — graph, DB, and profile HTTP mocked."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jobcopilot_agent.services.matching import run_resume_match
from jobcopilot_shared.exceptions import ExternalServiceError, NoActiveResumeError

_JOB_ID = uuid.uuid4()
_USER_ID = uuid.uuid4()
_TENANT_ID = uuid.uuid4()

_REPO = "jobcopilot_agent.services.matching.AnalysisRepository"
_FETCH = "jobcopilot_agent.services.matching._fetch_resume_text"
_GRAPH = "jobcopilot_agent.services.matching.resume_graph"


def _repo_with_analysis() -> MagicMock:
    analysis = MagicMock()
    analysis.id = uuid.uuid4()
    analysis.jd_structured = {"title": "Python Engineer"}
    repo = MagicMock()
    repo.get_by_job_user = AsyncMock(return_value=analysis)
    repo.update_analysis = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_no_active_resume_raises_before_graph() -> None:
    """Empty resume text must 409 BEFORE the graph (and its LLM call) runs."""
    session = AsyncMock()
    repo = _repo_with_analysis()

    with (
        patch(_REPO, return_value=repo),
        patch(_FETCH, new_callable=AsyncMock, return_value=""),
        patch(_GRAPH) as mock_graph,
    ):
        mock_graph.ainvoke = AsyncMock()
        with pytest.raises(NoActiveResumeError):
            await run_resume_match(session, _JOB_ID, _USER_ID, _TENANT_ID)

    mock_graph.ainvoke.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_profile_service_outage_raises_external_service_error() -> None:
    """A profile-service failure must not be misreported as 'no resume'."""
    session = AsyncMock()
    repo = _repo_with_analysis()

    with (
        patch(_REPO, return_value=repo),
        patch(_FETCH, new_callable=AsyncMock, side_effect=ExternalServiceError("down")),
        patch(_GRAPH) as mock_graph,
    ):
        mock_graph.ainvoke = AsyncMock()
        with pytest.raises(ExternalServiceError):
            await run_resume_match(session, _JOB_ID, _USER_ID, _TENANT_ID)

    mock_graph.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_analysis_returns_none() -> None:
    session = AsyncMock()
    repo = MagicMock()
    repo.get_by_job_user = AsyncMock(return_value=None)

    with patch(_REPO, return_value=repo):
        assert await run_resume_match(session, _JOB_ID, _USER_ID, _TENANT_ID) is None


@pytest.mark.asyncio
async def test_match_runs_graph_and_persists() -> None:
    session = AsyncMock()
    repo = _repo_with_analysis()

    graph_result = {
        "match_score": 77.0,
        "gap_analysis": {"hard_skills_gap": ["Go"]},
        "suggestions": [{"action": "Add Go projects"}],
    }

    with (
        patch(_REPO, return_value=repo),
        patch(_FETCH, new_callable=AsyncMock, return_value="Experienced Python engineer"),
        patch(_GRAPH) as mock_graph,
    ):
        mock_graph.ainvoke = AsyncMock(return_value=graph_result)
        outcome = await run_resume_match(session, _JOB_ID, _USER_ID, _TENANT_ID)

    assert outcome is not None
    assert outcome.match_score == 77.0
    repo.update_analysis.assert_awaited_once()
    session.commit.assert_awaited_once()
