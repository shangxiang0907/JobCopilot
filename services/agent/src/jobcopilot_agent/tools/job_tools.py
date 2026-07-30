"""ReAct tools for the AI assistant. User context is injected via RunnableConfig."""

import json
import logging
import uuid

import httpx
from jobcopilot_shared.metrics import record_degradation
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from jobcopilot_agent.config import settings
from jobcopilot_agent.deps import open_db_session
from jobcopilot_agent.services.analysis import run_job_analysis
from jobcopilot_agent.services.interview import prepare_interview_questions
from jobcopilot_agent.services.job_entry import add_job_and_analyze, scrape_job_url

log = logging.getLogger(__name__)


def _ctx(config: RunnableConfig) -> tuple[str, str]:
    """Extract (user_id, tenant_id) from RunnableConfig."""
    cfg = config.get("configurable", {})
    return cfg.get("user_id", ""), cfg.get("tenant_id", "")


def _service_error(resp: httpx.Response) -> str:
    """Extract a human-readable message from an error response."""
    try:
        data = resp.json()
    except Exception:
        return f"Service returned {resp.status_code}"
    error = data.get("error") or {}
    message = error.get("message") or data.get("detail")
    return str(message) if message else f"Service returned {resp.status_code}"


def _tool_failure(tool_name: str, reason: str, message: str) -> str:
    """The single exit for every tool failure — logged, counted, then reported.

    Tools cannot raise: an exception aborts the whole ReAct run, and the user
    loses the conversation over one bad call. So they return error JSON, which
    the model then narrates — and that is exactly why a failing tool looks like
    a working one from the outside (2026-07-08: four of five tools had been
    calling nonexistent endpoints since launch, with nothing in any dashboard).
    Routing every failure through here means a broken binding shows up as
    jobcopilot_degraded_operations_total{operation="agent_tool"} rising, before
    a user has to report that the assistant "sounds confident but is wrong".
    """
    log.warning("agent_tool_failed", extra={"tool": tool_name, "reason": reason})
    record_degradation(operation="agent_tool", reason=f"{tool_name}_{reason}")
    return json.dumps({"status": "error", "message": message})


@tool
async def analyze_job(job_id: str, config: RunnableConfig) -> str:
    """Run AI analysis on a tracked job: extract structured requirements from its
    description and compute a match score against the user's resume.

    Args:
        job_id: The UUID of the job to analyze (find it with search_jobs).
    """
    user_id, tenant_id = _ctx(config)
    try:
        job_uuid = uuid.UUID(job_id)
        user_uuid = uuid.UUID(user_id)
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        return _tool_failure("analyze_job", "bad_arguments", f"Invalid job_id '{job_id}'")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.job_service_url}/internal/jobs/{job_id}")
        # A job in another tenant must look identical to a missing one.
        if resp.status_code != 200:
            return _tool_failure("analyze_job", "job_lookup_failed", _service_error(resp))
        job = resp.json()
        if job.get("tenant_id") != tenant_id:
            return _tool_failure("analyze_job", "not_found", f"Job {job_id} not found")

        raw_text = job.get("raw_jd") or ""
        if not raw_text:
            return _tool_failure(
                "analyze_job", "no_jd_text", "This job has no description text to analyze."
            )

        async with open_db_session() as session:
            outcome = await run_job_analysis(
                session,
                job_id=job_uuid,
                user_id=user_uuid,
                tenant_id=tenant_uuid,
                url=job.get("url", ""),
                title=job.get("title", ""),
                company_name=job.get("company_name", ""),
                location=job.get("location") or "",
                raw_text=raw_text,
            )
        return json.dumps(
            {
                "status": outcome.status,
                "job_id": job_id,
                "match_score": outcome.match_score,
                "skills_required": outcome.skills_required[:10],
            }
        )
    except Exception as exc:
        return _tool_failure("analyze_job", "unexpected_error", str(exc))


@tool
async def update_kanban(job_id: str, status: str, config: RunnableConfig) -> str:
    """Update the status of a job application on the kanban board.

    Args:
        job_id: The UUID of the job whose application status to update.
        status: New status — discovered, applied, interviewing, offer, rejected, or withdrawn.
    """
    user_id, tenant_id = _ctx(config)
    valid_statuses = {"discovered", "applied", "interviewing", "offer", "rejected", "withdrawn"}
    if status not in valid_statuses:
        return _tool_failure(
            "update_kanban",
            "bad_arguments",
            f"Invalid status '{status}'. Valid: {sorted(valid_statuses)}",
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{settings.job_service_url}/internal/applications/by-job/{job_id}",
                json={"status": status, "user_id": user_id, "tenant_id": tenant_id},
            )
        if resp.status_code == 200:
            return json.dumps({"status": "updated", "job_id": job_id, "new_status": status})
        return _tool_failure("update_kanban", "rejected", _service_error(resp))
    except Exception as exc:
        return _tool_failure("update_kanban", "unexpected_error", str(exc))


@tool
async def search_jobs(query: str, config: RunnableConfig) -> str:
    """Search for job postings matching a query.

    Args:
        query: Search terms, e.g. 'Python backend engineer remote'.
    """
    _user_id, tenant_id = _ctx(config)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.job_service_url}/internal/jobs",
                params={"q": query, "tenant_id": tenant_id, "limit": 5},
            )
        if resp.status_code == 200:
            jobs = resp.json().get("items", [])
            summary = [
                {
                    "job_id": j.get("job_id"),
                    "title": j.get("title"),
                    "company": j.get("company_name"),
                    "location": j.get("location"),
                }
                for j in jobs
            ]
            return json.dumps({"jobs": summary, "total": len(summary)})
        return _tool_failure("search_jobs", "rejected", _service_error(resp))
    except Exception as exc:
        return _tool_failure("search_jobs", "unexpected_error", str(exc))


@tool
async def get_applications(config: RunnableConfig, status: str = "") -> str:
    """Retrieve the user's job applications, optionally filtered by status.

    Args:
        status: Optional status filter (discovered, applied, interviewing, offer,
                rejected, withdrawn). Leave empty to get all applications.
    """
    user_id, tenant_id = _ctx(config)
    params: dict[str, str | int] = {"user_id": user_id, "tenant_id": tenant_id, "limit": 10}
    if status:
        params["status"] = status
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.job_service_url}/internal/applications",
                params=params,
            )
        if resp.status_code == 200:
            apps = resp.json().get("items", [])
            summary = [
                {
                    "application_id": a.get("application_id"),
                    "job_id": a.get("job_id"),
                    "job_title": (a.get("job") or {}).get("title"),
                    "company": (a.get("job") or {}).get("company_name"),
                    "status": a.get("status"),
                    "match_score": a.get("match_score"),
                }
                for a in apps
            ]
            return json.dumps({"applications": summary, "total": len(summary)})
        return _tool_failure("get_applications", "rejected", _service_error(resp))
    except Exception as exc:
        return _tool_failure("get_applications", "unexpected_error", str(exc))


@tool
async def prepare_interview(job_id: str, config: RunnableConfig) -> str:
    """Generate interview preparation materials for a specific job.

    Args:
        job_id: The UUID of the job to prepare interview questions for.
    """
    user_id, tenant_id = _ctx(config)
    try:
        job_uuid = uuid.UUID(job_id)
        user_uuid = uuid.UUID(user_id)
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        return _tool_failure("prepare_interview", "bad_arguments", f"Invalid job_id '{job_id}'")

    try:
        async with open_db_session() as session:
            prep = await prepare_interview_questions(session, job_uuid, user_uuid, tenant_uuid)
        if prep is None:
            return _tool_failure(
                "prepare_interview",
                "no_analysis",
                "No analysis found for this job. Run analyze_job first.",
            )
        questions = prep.behavioral_questions + prep.technical_questions
        return json.dumps(
            {
                "status": "ready",
                "job_id": job_id,
                "question_count": len(questions),
                "preview": questions[:2],
            }
        )
    except Exception as exc:
        return _tool_failure("prepare_interview", "unexpected_error", str(exc))


@tool
async def add_job_from_url(url: str, config: RunnableConfig) -> str:
    """Add a job posting to the user's list by fetching a URL, then analyze it.
    Works with any public job page. If the page cannot be fetched (login wall,
    anti-bot), tell the user to paste the job description text instead — then
    call add_job_from_text with it.

    Args:
        url: The job posting URL, e.g. https://example.com/careers/123.
    """
    user_id, tenant_id = _ctx(config)
    try:
        user_uuid = uuid.UUID(user_id)
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        return _tool_failure("add_job_from_url", "bad_arguments", "Missing user context")

    try:
        scraped = await scrape_job_url(url)
        if not scraped.get("ok"):
            return json.dumps(
                {
                    "status": "scrape_failed",
                    "message": str(scraped.get("error", "fetch failed")),
                    "hint": "Ask the user to paste the job description text instead.",
                }
            )

        async with open_db_session() as session:
            outcome = await add_job_and_analyze(
                session,
                user_id=user_uuid,
                tenant_id=tenant_uuid,
                raw_text=str(scraped.get("text", "")),
                url=url,
                title=str(scraped.get("title", "")),
            )
        if not outcome.ok and not outcome.job_id:
            return _tool_failure("add_job_from_url", "add_failed", str(outcome.error))
        return json.dumps(
            {
                "status": "added",
                "job_id": outcome.job_id,
                "title": outcome.title,
                "company": outcome.company_name,
                "match_score": outcome.match_score,
                "skills_required": outcome.skills_required,
            }
        )
    except Exception as exc:
        return _tool_failure("add_job_from_url", "unexpected_error", str(exc))


@tool
async def add_job_from_text(
    jd_text: str, config: RunnableConfig, title: str = "", company_name: str = ""
) -> str:
    """Add a job posting from pasted job-description text, then analyze it.
    Use when the user pastes a JD directly, when a screenshot was transcribed,
    or as the fallback after add_job_from_url fails.

    Args:
        jd_text: The full job description text.
        title: Job title if known (otherwise extracted by analysis).
        company_name: Company name if known.
    """
    user_id, tenant_id = _ctx(config)
    try:
        user_uuid = uuid.UUID(user_id)
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        return _tool_failure("add_job_from_text", "bad_arguments", "Missing user context")

    if len(jd_text.strip()) < 50:
        return _tool_failure(
            "add_job_from_text", "jd_too_short", "Job description text is too short to analyze."
        )

    try:
        async with open_db_session() as session:
            outcome = await add_job_and_analyze(
                session,
                user_id=user_uuid,
                tenant_id=tenant_uuid,
                raw_text=jd_text,
                title=title,
                company_name=company_name,
            )
        if not outcome.ok and not outcome.job_id:
            return _tool_failure("add_job_from_text", "add_failed", str(outcome.error))
        return json.dumps(
            {
                "status": "added",
                "job_id": outcome.job_id,
                "title": outcome.title,
                "company": outcome.company_name,
                "match_score": outcome.match_score,
                "skills_required": outcome.skills_required,
            }
        )
    except Exception as exc:
        return _tool_failure("add_job_from_text", "unexpected_error", str(exc))


ALL_TOOLS = [
    analyze_job,
    update_kanban,
    search_jobs,
    get_applications,
    prepare_interview,
    add_job_from_url,
    add_job_from_text,
]
