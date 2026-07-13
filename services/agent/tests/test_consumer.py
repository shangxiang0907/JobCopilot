"""Unit tests for the job.discovered consumer — HTTP mocked.

Regression focus (owner decision 2026-07-13): ingest is LLM-FREE. The
consumer only upserts jobs; any AnalyzerGraph invocation on this path is a
token-cost regression (one discovery run = 100+ jobs).
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jobcopilot_agent.services.consumer import _process_job_message

_USER_ID = str(uuid.uuid4())
_TENANT_ID = str(uuid.uuid4())
_JOB_ID = str(uuid.uuid4())

_BODY = {
    "user_id": _USER_ID,
    "tenant_id": _TENANT_ID,
    "run_id": "run-1",
    "url": "https://example.com/jobs/view/123",
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
    return client


def _upsert_payload(client: AsyncMock) -> dict[str, Any]:
    assert client.post.await_args is not None
    payload: dict[str, Any] = client.post.await_args.kwargs["json"]
    return payload


@pytest.mark.asyncio
async def test_ingest_upserts_without_any_llm_analysis() -> None:
    client = _mock_http_client()

    with patch("jobcopilot_agent.services.consumer.httpx.AsyncClient", return_value=client):
        await _process_job_message(_BODY)

    client.post.assert_awaited_once()
    payload = _upsert_payload(client)
    assert payload["url"] == _BODY["url"]
    assert payload["tenant_id"] == _TENANT_ID
    assert payload["source"] == "discovery"
    # LLM-free ingest: nothing beyond the single upsert POST may happen.
    client.patch.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingest_never_imports_analyzer() -> None:
    """The consumer module must not reference the analysis pipeline at all —
    the import itself is the tripwire for reintroducing analyze-on-ingest."""
    import jobcopilot_agent.services.consumer as consumer_module

    assert not hasattr(consumer_module, "run_job_analysis")


@pytest.mark.asyncio
async def test_upsert_failure_is_logged_not_raised() -> None:
    client = _mock_http_client(post_status=500)

    with patch("jobcopilot_agent.services.consumer.httpx.AsyncClient", return_value=client):
        await _process_job_message(_BODY)  # must not raise

    client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_malformed_message_is_dropped() -> None:
    """Payloads violating the shared JobDiscoveredEvent contract are poison messages."""
    client = _mock_http_client()
    with patch("jobcopilot_agent.services.consumer.httpx.AsyncClient", return_value=client):
        # missing required fields entirely → ValidationError path
        await _process_job_message({"url": "https://example.com"})
        # present but empty identity → guard path
        await _process_job_message(
            {
                "url": "https://example.com",
                "user_id": "",
                "tenant_id": "",
                "run_id": "r",
                "title": "t",
                "company_name": "c",
            }
        )

    client.post.assert_not_awaited()
