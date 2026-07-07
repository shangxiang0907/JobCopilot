"""Unit tests for the job.discovered consumer — HTTP, DB, and graph mocked.

Regression focus: the analysis must be keyed by the job_id RETURNED by Job
Service (the MQ payload carries none), not a locally generated one.
"""

import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jobcopilot_agent.services.analysis import JobAnalysisOutcome
from jobcopilot_agent.services.consumer import _process_job_message

_USER_ID = str(uuid.uuid4())
_TENANT_ID = str(uuid.uuid4())
_JOB_ID = str(uuid.uuid4())

_BODY = {
    "user_id": _USER_ID,
    "tenant_id": _TENANT_ID,
    "url": "https://linkedin.com/jobs/view/123",
    "title": "Backend Engineer",
    "company_name": "Acme",
    "location": "Remote",
    "raw_text": "We are hiring...",
}


def _mock_http_client(post_status: int = 200) -> AsyncMock:
    post_resp = MagicMock()
    post_resp.status_code = post_status
    post_resp.json.return_value = {"job_id": _JOB_ID}
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(return_value=post_resp)
    client.patch = AsyncMock(return_value=MagicMock(status_code=200))
    return client


@asynccontextmanager
async def _fake_session() -> Any:
    yield AsyncMock()


@pytest.mark.asyncio
async def test_analysis_keyed_by_job_service_job_id() -> None:
    outcome = JobAnalysisOutcome(
        analysis_id=uuid.uuid4(),
        jd_structured={"title": "Backend Engineer"},
        skills_required=["Python"],
        match_score=70.0,
        status="done",
    )
    client = _mock_http_client()

    with (
        patch("jobcopilot_agent.services.consumer.httpx.AsyncClient", return_value=client),
        patch("jobcopilot_agent.services.consumer.open_db_session", _fake_session),
        patch(
            "jobcopilot_agent.services.consumer.run_job_analysis",
            new_callable=AsyncMock,
            return_value=outcome,
        ) as mock_run,
    ):
        await _process_job_message(_BODY)

    # Job upserted first, analysis keyed by the returned job_id
    client.post.assert_awaited_once()
    assert mock_run.await_args is not None
    assert mock_run.await_args.kwargs["job_id"] == uuid.UUID(_JOB_ID)
    # Structured analysis pushed back onto the job record
    assert client.patch.await_args is not None
    patch_url = client.patch.await_args.args[0]
    assert patch_url.endswith(f"/internal/jobs/{_JOB_ID}")


@pytest.mark.asyncio
async def test_no_analysis_when_job_upsert_fails() -> None:
    client = _mock_http_client(post_status=500)

    with (
        patch("jobcopilot_agent.services.consumer.httpx.AsyncClient", return_value=client),
        patch("jobcopilot_agent.services.consumer.open_db_session", _fake_session),
        patch(
            "jobcopilot_agent.services.consumer.run_job_analysis",
            new_callable=AsyncMock,
        ) as mock_run,
    ):
        await _process_job_message(_BODY)

    mock_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_message_without_identity_is_dropped() -> None:
    client = _mock_http_client()
    with (
        patch("jobcopilot_agent.services.consumer.httpx.AsyncClient", return_value=client),
        patch(
            "jobcopilot_agent.services.consumer.run_job_analysis",
            new_callable=AsyncMock,
        ) as mock_run,
    ):
        await _process_job_message({"url": "https://example.com", "user_id": "", "tenant_id": ""})

    client.post.assert_not_awaited()
    mock_run.assert_not_awaited()
