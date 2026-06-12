"""ReAct tools for the AI assistant. User context is injected via RunnableConfig."""

import json
import logging

import httpx
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from jobcopilot_agent.config import settings

log = logging.getLogger(__name__)


def _ctx(config: RunnableConfig) -> tuple[str, str]:
    """Extract (user_id, tenant_id) from RunnableConfig."""
    cfg = config.get("configurable", {})
    return cfg.get("user_id", ""), cfg.get("tenant_id", "")


@tool
async def analyze_job(url: str, config: RunnableConfig) -> str:
    """Analyze a job posting from its URL. Fetches the job and runs the full AI analysis pipeline.

    Args:
        url: The full URL of the job posting to analyze.
    """
    user_id, tenant_id = _ctx(config)
    payload = {"url": url, "user_id": user_id, "tenant_id": tenant_id}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.job_service_url}/internal/jobs/analyze",
                json=payload,
            )
        if resp.status_code in (200, 202):
            data = resp.json()
            return json.dumps({"status": "queued", "job_id": data.get("job_id"), "url": url})
        return json.dumps({"status": "error", "message": f"Service returned {resp.status_code}"})
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
        return json.dumps({"status": "error", "message": f"Service returned {resp.status_code}"})
    except Exception as exc:
        log.warning("update_kanban_tool_failed", extra={"error": str(exc)})
        return json.dumps({"status": "error", "message": str(exc)})


@tool
async def search_jobs(query: str, config: RunnableConfig) -> str:
    """Search for job postings matching a query.

    Args:
        query: Search terms, e.g. 'Python backend engineer remote'.
    """
    user_id, tenant_id = _ctx(config)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.job_service_url}/internal/jobs",
                params={"q": query, "user_id": user_id, "tenant_id": tenant_id, "limit": 5},
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
        return json.dumps({"jobs": [], "total": 0})
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
    params: dict = {"user_id": user_id, "tenant_id": tenant_id, "limit": 10}
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
                    "job_title": a.get("job_title"),
                    "company": a.get("company_name"),
                    "status": a.get("status"),
                    "match_score": a.get("match_score"),
                }
                for a in apps
            ]
            return json.dumps({"applications": summary, "total": len(summary)})
        return json.dumps({"applications": [], "total": 0})
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
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "http://localhost:8000/v1/agent/interview",
                json={"job_id": job_id},
                headers={"X-User-Id": user_id, "X-Tenant-Id": tenant_id},
            )
        if resp.status_code == 200:
            data = resp.json()
            questions = data.get("questions", [])
            return json.dumps(
                {
                    "status": "ready",
                    "job_id": job_id,
                    "question_count": len(questions),
                    "preview": questions[:2] if questions else [],
                }
            )
        return json.dumps({"status": "error", "message": f"Service returned {resp.status_code}"})
    except Exception as exc:
        log.warning("prepare_interview_tool_failed", extra={"error": str(exc)})
        return json.dumps({"status": "error", "message": str(exc)})


ALL_TOOLS = [analyze_job, update_kanban, search_jobs, get_applications, prepare_interview]
