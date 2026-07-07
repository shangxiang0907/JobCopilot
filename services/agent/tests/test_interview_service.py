"""Unit tests for the shared interview preparation service — graph and DB mocked."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jobcopilot_agent.services.interview import prepare_interview_questions

_JOB_ID = uuid.uuid4()
_USER_ID = uuid.uuid4()
_TENANT_ID = uuid.uuid4()


def _make_repo(analysis: MagicMock | None) -> MagicMock:
    repo = MagicMock()
    repo.get_by_job_user = AsyncMock(return_value=analysis)
    repo.update_analysis = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_returns_none_without_prior_analysis() -> None:
    session = AsyncMock()
    repo = _make_repo(None)

    with patch("jobcopilot_agent.services.interview.AnalysisRepository", return_value=repo):
        result = await prepare_interview_questions(session, _JOB_ID, _USER_ID, _TENANT_ID)

    assert result is None
    repo.update_analysis.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_runs_graph_persists_and_commits() -> None:
    analysis = MagicMock()
    analysis.id = uuid.uuid4()
    analysis.jd_structured = {"title": "Python Engineer", "skills_required": ["Python"]}

    session = AsyncMock()
    repo = _make_repo(analysis)
    behavioral = [{"question": "Tell me about a challenge", "reference_answer": "STAR"}]
    technical = [{"question": "Explain asyncio", "reference_answer": "Event loop"}]

    with (
        patch("jobcopilot_agent.services.interview.AnalysisRepository", return_value=repo),
        patch("jobcopilot_agent.services.interview.interview_graph") as mock_graph,
    ):
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "behavioral_questions": behavioral,
                "technical_questions": technical,
            }
        )
        result = await prepare_interview_questions(session, _JOB_ID, _USER_ID, _TENANT_ID)

    assert result is not None
    assert result.analysis_id == analysis.id
    assert result.behavioral_questions == behavioral
    assert result.technical_questions == technical

    repo.update_analysis.assert_awaited_once_with(
        analysis,
        interview_questions={"behavioral": behavioral, "technical": technical},
        status="done",
    )
    session.commit.assert_awaited_once()
