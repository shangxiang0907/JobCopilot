"""ReAct tools for the AI assistant. User context is injected via RunnableConfig."""

import json
import logging
import uuid

import httpx
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from jobcopilot_agent.config import settings
from jobcopilot_agent.deps import open_db_session
from jobcopilot_agent.services.analysis import run_job_analysis
from jobcopilot_agent.services.interview import prepare_interview_questions

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
        return json.dumps({"status": "error", "message": f"Invalid job_id '{job_id}'"})

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.job_service_url}/internal/jobs/{job_id}")
        # A job in another tenant must look identical to a missing one.
        if resp.status_code != 200:
            return json.dumps({"status": "error", "message": _service_error(resp)})
        job = resp.json()
        if job.get("tenant_id") != tenant_id:
            return json.dumps({"status": "error", "message": f"Job {job_id} not found"})

        raw_text = job.get("raw_jd") or ""
        if not raw_text:
            return json.dumps(
                {"status": "error", "message": "This job has no description text to analyze."}
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
        log.warning("analyze_job_tool_failed", extra={"error": str(exc)})
        return json.dumps({"status": "error", "message": str(exc)})


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
        return json.dumps(
            {
                "status": "error",
                "message": f"Invalid status '{status}'. Valid: {sorted(valid_statuses)}",
            }
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{settings.job_service_url}/internal/applications/by-job/{job_id}",
                json={"status": status, "user_id": user_id, "tenant_id": tenant_id},
            )
        if resp.status_code == 200:
            return json.dumps({"status": "updated", "job_id": job_id, "new_status": status})
        return json.dumps({"status": "error", "message": _service_error(resp)})
    except Exception as exc:
        log.warning("update_kanban_tool_failed", extra={"error": str(exc)})
        return json.dumps({"status": "error", "message": str(exc)})


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
        return json.dumps({"status": "error", "message": _service_error(resp)})
    except Exception as exc:
        log.warning("search_jobs_tool_failed", extra={"error": str(exc)})
        return json.dumps({"status": "error", "message": str(exc)})


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
        return json.dumps({"status": "error", "message": _service_error(resp)})
    except Exception as exc:
        log.warning("get_applications_tool_failed", extra={"error": str(exc)})
        return json.dumps({"status": "error", "message": str(exc)})


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
        return json.dumps({"status": "error", "message": f"Invalid job_id '{job_id}'"})

    try:
        async with open_db_session() as session:
            prep = await prepare_interview_questions(session, job_uuid, user_uuid, tenant_uuid)
        if prep is None:
            return json.dumps(
                {
                    "status": "error",
                    "message": "No analysis found for this job. Run analyze_job first.",
                }
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
        log.warning("prepare_interview_tool_failed", extra={"error": str(exc)})
        return json.dumps({"status": "error", "message": str(exc)})


ALL_TOOLS = [analyze_job, update_kanban, search_jobs, get_applications, prepare_interview]
