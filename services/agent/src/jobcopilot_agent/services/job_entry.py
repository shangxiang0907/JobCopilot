"""Manual JD entry paths (PRD 3.1): URL scrape / pasted text / screenshot.

Shared by the ReAct tools and the chat endpoint. All three paths converge on
the same pipeline: obtain JD text → upsert the job in Job Service (idempotent
by URL) → run in-process analysis.
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass

import httpx
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from jobcopilot_agent.config import settings
from jobcopilot_agent.services.analysis import run_job_analysis
from jobcopilot_agent.services.llm import get_vision_llm

# stdlib logging like every other agent module — a bare structlog logger here
# binds a PrintLogger to whichever stdout exists at first use, which under the
# full pytest suite is a closed capture stream (CI-only failure, 2026-07-14).
log = logging.getLogger(__name__)

_TRANSCRIBE_PROMPT = (
    "Transcribe the job posting in this image into plain text. Include the job "
    "title, company, location, and the full description. Output ONLY the "
    "transcribed text, no commentary. If the image contains no job posting, "
    "output exactly: NO_JOB_POSTING_FOUND"
)


@dataclass
class JobEntryOutcome:
    ok: bool
    job_id: str = ""
    title: str = ""
    company_name: str = ""
    match_score: float = 0.0
    skills_required: list[str] | None = None
    error: str = ""


async def scrape_job_url(url: str) -> dict[str, str | bool]:
    """Delegate URL fetching to Discovery Service (owns Playwright)."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.discovery_service_url}/internal/scrape", json={"url": url}
        )
    resp.raise_for_status()
    data: dict[str, str | bool] = resp.json()
    return data


async def transcribe_jd_image(image_data_url: str) -> str:
    """Vision-model transcription of a JD screenshot. Empty string = no JD found."""
    message = HumanMessage(
        content=[
            {"type": "text", "text": _TRANSCRIBE_PROMPT},
            {"type": "image_url", "image_url": {"url": image_data_url}},
        ]
    )
    response = await get_vision_llm().ainvoke([message])
    text = response.content if isinstance(response.content, str) else ""
    if "NO_JOB_POSTING_FOUND" in text:
        return ""
    return text.strip()


async def add_job_and_analyze(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    raw_text: str,
    url: str = "",
    title: str = "",
    company_name: str = "",
    source: str = "manual",
) -> JobEntryOutcome:
    """Upsert the job in Job Service, then run in-process analysis.

    Text/screenshot entries have no URL: a synthetic stable `manual://<hash>`
    key keeps the upsert idempotent for repeated pastes of the same JD.
    """
    if not url:
        digest = hashlib.sha256(raw_text.encode()).hexdigest()[:16]
        url = f"manual://{digest}"

    payload = {
        "tenant_id": str(tenant_id),
        "title": title or "Untitled position",
        "company_name": company_name or "Unknown company",
        "url": url,
        "source": source,
        "raw_jd": raw_text,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{settings.job_service_url}/internal/jobs", json=payload)
    if resp.status_code not in (200, 201):
        log.warning(
            "job_upsert_failed", extra={"status": resp.status_code, "body": resp.text[:200]}
        )
        return JobEntryOutcome(ok=False, error=f"Job Service returned {resp.status_code}")
    job = resp.json()
    job_id = uuid.UUID(job["job_id"])

    outcome = await run_job_analysis(
        session,
        job_id=job_id,
        user_id=user_id,
        tenant_id=tenant_id,
        url=url,
        title=job.get("title", title),
        company_name=job.get("company_name", company_name),
        location=job.get("location") or "",
        raw_text=raw_text,
    )

    structured = outcome.jd_structured or {}
    return JobEntryOutcome(
        ok=outcome.status == "done",
        job_id=str(job_id),
        title=structured.get("title") or job.get("title", ""),
        company_name=structured.get("company") or job.get("company_name", ""),
        match_score=outcome.match_score,
        skills_required=outcome.skills_required[:10],
        error="" if outcome.status == "done" else "analysis failed",
    )
