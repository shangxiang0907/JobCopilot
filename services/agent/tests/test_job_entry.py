"""Unit tests for the manual JD entry pipeline — HTTP and LLMs fully mocked.

Token-frugality note: these tests exist so the URL/text/screenshot paths are
verified WITHOUT live LLM calls (see CLAUDE.md, LLM/AI section).
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jobcopilot_agent.services.analysis import JobAnalysisOutcome
from jobcopilot_agent.services.job_entry import add_job_and_analyze, transcribe_jd_image

_USER = uuid.uuid4()
_TENANT = uuid.uuid4()
_JOB_ID = str(uuid.uuid4())


def _mock_client(post_status: int = 200, job: dict[str, Any] | None = None) -> AsyncMock:
    resp = MagicMock()
    resp.status_code = post_status
    resp.json.return_value = job or {"job_id": _JOB_ID, "title": "Engineer", "company_name": "Acme"}
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(return_value=resp)
    return client


def _outcome(status: str = "done") -> JobAnalysisOutcome:
    return JobAnalysisOutcome(
        analysis_id=uuid.uuid4(),
        jd_structured={"title": "Engineer", "company": "Acme"},
        skills_required=["Python"],
        match_score=77.0,
        status=status,
    )


@pytest.mark.asyncio
async def test_text_entry_generates_stable_synthetic_url() -> None:
    client = _mock_client()
    with (
        patch("jobcopilot_agent.services.job_entry.httpx.AsyncClient", return_value=client),
        patch(
            "jobcopilot_agent.services.job_entry.run_job_analysis",
            new_callable=AsyncMock,
            return_value=_outcome(),
        ),
    ):
        await add_job_and_analyze(
            AsyncMock(), user_id=_USER, tenant_id=_TENANT, raw_text="We hire Python devs. " * 10
        )
        first_url = client.post.await_args.kwargs["json"]["url"]
        await add_job_and_analyze(
            AsyncMock(), user_id=_USER, tenant_id=_TENANT, raw_text="We hire Python devs. " * 10
        )
        second_url = client.post.await_args.kwargs["json"]["url"]

    assert first_url.startswith("manual://")
    # Same pasted text → same synthetic URL → idempotent upsert.
    assert first_url == second_url


@pytest.mark.asyncio
async def test_url_entry_keeps_real_url_and_returns_analysis() -> None:
    client = _mock_client()
    with (
        patch("jobcopilot_agent.services.job_entry.httpx.AsyncClient", return_value=client),
        patch(
            "jobcopilot_agent.services.job_entry.run_job_analysis",
            new_callable=AsyncMock,
            return_value=_outcome(),
        ) as mock_run,
    ):
        outcome = await add_job_and_analyze(
            AsyncMock(),
            user_id=_USER,
            tenant_id=_TENANT,
            raw_text="Long enough JD text for analysis.",
            url="https://example.com/jobs/1",
            title="Engineer",
        )

    assert client.post.await_args is not None
    assert client.post.await_args.kwargs["json"]["url"] == "https://example.com/jobs/1"
    assert mock_run.await_args is not None
    assert mock_run.await_args.kwargs["job_id"] == uuid.UUID(_JOB_ID)
    assert outcome.ok and outcome.match_score == 77.0


@pytest.mark.asyncio
async def test_upsert_failure_short_circuits_without_analysis() -> None:
    client = _mock_client(post_status=500)
    with (
        patch("jobcopilot_agent.services.job_entry.httpx.AsyncClient", return_value=client),
        patch(
            "jobcopilot_agent.services.job_entry.run_job_analysis",
            new_callable=AsyncMock,
        ) as mock_run,
    ):
        outcome = await add_job_and_analyze(
            AsyncMock(), user_id=_USER, tenant_id=_TENANT, raw_text="x" * 100
        )

    assert not outcome.ok and "500" in outcome.error
    mock_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_transcribe_returns_empty_when_no_job_found() -> None:
    vision = AsyncMock()
    vision.ainvoke = AsyncMock(return_value=MagicMock(content="NO_JOB_POSTING_FOUND"))
    with patch("jobcopilot_agent.services.job_entry.get_vision_llm", return_value=vision):
        assert await transcribe_jd_image("data:image/png;base64,xxxx") == ""


@pytest.mark.asyncio
async def test_transcribe_returns_text() -> None:
    vision = AsyncMock()
    vision.ainvoke = AsyncMock(return_value=MagicMock(content="Acme — Senior Engineer\nRemote"))
    with patch("jobcopilot_agent.services.job_entry.get_vision_llm", return_value=vision):
        text = await transcribe_jd_image("data:image/png;base64,xxxx")
    assert "Senior Engineer" in text
