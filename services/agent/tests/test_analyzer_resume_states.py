"""The analyzer must keep three resume outcomes distinct.

    profile service unreachable / errored -> resume_status "unavailable"
    user genuinely has no default resume   -> resume_status "absent"
    resume text retrieved                  -> resume_status "ok"

All three used to produce resume_text="" and a match_score of 0.0. A user
reading "0% match" concludes the job is a bad fit and discards it, when the
truth may be that the profile service was down for ten seconds. This is the
failure class CLAUDE.md forbids: mapping an error onto a business-legal value.

The sibling reference implementation is services/matching.py::_fetch_resume_text,
which raises on transport failure because a match has no payload without the
resume. The analyzer degrades instead: its payload is the structured JD, which
needs no resume, so an outage should cost the score and not the whole analysis.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from jobcopilot_agent.graphs.analyzer_graph import _compute_match_node, _fetch_resume_node


def _state(**overrides: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "job_id": "job-1",
        "user_id": "user-1",
        "tenant_id": "tenant-1",
        "url": "https://example.com/jobs/1",
        "title": "Engineer",
        "company_name": "Acme",
        "location": "Remote",
        "raw_text": "We need an engineer.",
        "resume_text": "",
        "resume_status": "unavailable",
        "jd_structured": {},
        "skills_required": [],
        "match_score": None,
        "error": None,
    }
    state.update(overrides)
    return state


def _client_returning(resp: MagicMock) -> MagicMock:
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.get = AsyncMock(return_value=resp)
    return MagicMock(return_value=client)


def _client_raising(exc: Exception) -> MagicMock:
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.get = AsyncMock(side_effect=exc)
    return MagicMock(return_value=client)


@pytest.mark.asyncio
async def test_resume_text_present_is_ok() -> None:
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"default_resume_text": "Senior Python engineer"}
    with patch("jobcopilot_agent.graphs.analyzer_graph.httpx.AsyncClient", _client_returning(resp)):
        result = await _fetch_resume_node(_state())  # type: ignore[arg-type]

    assert result["resume_status"] == "ok"
    assert result["resume_text"] == "Senior Python engineer"


@pytest.mark.asyncio
async def test_user_without_a_default_resume_is_absent_not_unavailable() -> None:
    """A successful read of a user who has no resume is not a service failure."""
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"default_resume_text": ""}
    with (
        patch("jobcopilot_agent.graphs.analyzer_graph.httpx.AsyncClient", _client_returning(resp)),
        patch("jobcopilot_agent.graphs.analyzer_graph.record_degradation") as metric,
    ):
        result = await _fetch_resume_node(_state())  # type: ignore[arg-type]

    assert result["resume_status"] == "absent"
    metric.assert_called_once_with(operation="job_analysis", reason="no_default_resume")


@pytest.mark.asyncio
async def test_transport_failure_is_unavailable_not_absent() -> None:
    """A ten-second outage must never be reported as "you have no resume"."""
    with (
        patch(
            "jobcopilot_agent.graphs.analyzer_graph.httpx.AsyncClient",
            _client_raising(httpx.ConnectError("connection refused")),
        ),
        patch("jobcopilot_agent.graphs.analyzer_graph.record_degradation") as metric,
    ):
        result = await _fetch_resume_node(_state())  # type: ignore[arg-type]

    assert result["resume_status"] == "unavailable"
    metric.assert_called_once_with(operation="job_analysis", reason="profile_service_unreachable")


@pytest.mark.asyncio
async def test_non_200_is_unavailable() -> None:
    with (
        patch(
            "jobcopilot_agent.graphs.analyzer_graph.httpx.AsyncClient",
            _client_returning(MagicMock(status_code=500)),
        ),
        patch("jobcopilot_agent.graphs.analyzer_graph.record_degradation") as metric,
    ):
        result = await _fetch_resume_node(_state())  # type: ignore[arg-type]

    assert result["resume_status"] == "unavailable"
    metric.assert_called_once_with(operation="job_analysis", reason="profile_service_error")


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["absent", "unavailable"])
async def test_no_usable_resume_yields_no_score_and_no_llm_call(status: str) -> None:
    """Fail before the LLM, never after — an unscorable job costs zero tokens."""
    with patch("jobcopilot_agent.graphs.analyzer_graph.get_llm") as get_llm:
        result = await _compute_match_node(
            _state(resume_status=status, jd_structured={"title": "Engineer"})  # type: ignore[arg-type]
        )

    assert result["match_score"] is None
    get_llm.assert_not_called()


@pytest.mark.asyncio
async def test_missing_jd_structure_yields_no_score() -> None:
    with patch("jobcopilot_agent.graphs.analyzer_graph.get_llm") as get_llm:
        result = await _compute_match_node(
            _state(resume_status="ok", resume_text="Python engineer", jd_structured={})  # type: ignore[arg-type]
        )

    assert result["match_score"] is None
    get_llm.assert_not_called()


@pytest.mark.asyncio
async def test_scoring_failure_yields_none_rather_than_zero() -> None:
    """A failed scoring call is not a verdict of "worst possible match"."""
    llm = AsyncMock()
    llm.bind = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(side_effect=RuntimeError("provider timeout"))
    with (
        patch("jobcopilot_agent.graphs.analyzer_graph.get_llm", return_value=llm),
        patch("jobcopilot_agent.graphs.analyzer_graph.record_degradation") as metric,
    ):
        result = await _compute_match_node(
            _state(  # type: ignore[arg-type]
                resume_status="ok",
                resume_text="Python engineer",
                jd_structured={"title": "Engineer"},
            )
        )

    assert result["match_score"] is None
    metric.assert_called_once_with(operation="job_analysis", reason="match_score_llm_failed")
