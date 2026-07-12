"""
AnalyzerGraph — extracts structured JD fields and computes a quick match score.

Nodes:
  1. extract_structure  → LLM JSON → jd_structured + skills_required
  2. compute_match      → LLM JSON (job vs resume) → match_score
"""

import json
import logging
from typing import Any, TypedDict

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from jobcopilot_agent.config import settings
from jobcopilot_agent.graphs._content import response_text
from jobcopilot_agent.graphs.llm_outputs import JDStructure, MatchScoreOutput
from jobcopilot_agent.prompts.analyzer import (
    EXTRACT_STRUCTURE_SYSTEM,
    EXTRACT_STRUCTURE_USER,
    MATCH_SCORE_SYSTEM,
    MATCH_SCORE_USER,
)
from jobcopilot_agent.services.llm import get_llm

log = logging.getLogger(__name__)

_JSON_MODE = {"response_format": {"type": "json_object"}}


class AnalyzerState(TypedDict):
    # Inputs
    job_id: str
    user_id: str
    tenant_id: str
    url: str
    title: str
    company_name: str
    location: str
    raw_text: str
    # Intermediate
    resume_text: str
    # Outputs
    jd_structured: dict[str, Any]
    skills_required: list[str]
    match_score: float
    error: str | None


async def _fetch_resume_node(state: AnalyzerState) -> dict[str, Any]:
    """Fetch the user's active resume from Profile Service."""
    if not state.get("raw_text"):
        return {"error": "No raw_text provided", "resume_text": ""}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.profile_service_url}/internal/profiles/{state['user_id']}"
            )
        if resp.status_code == 200:
            data = resp.json()
            return {"resume_text": data.get("active_resume_text") or ""}
    except Exception as exc:
        log.warning("resume_fetch_failed", extra={"error": str(exc), "user_id": state["user_id"]})

    return {"resume_text": ""}


async def _extract_structure_node(state: AnalyzerState) -> dict[str, Any]:
    """Use LLM to extract structured fields from raw JD text."""
    llm = get_llm().bind(**_JSON_MODE)
    messages = [
        SystemMessage(content=EXTRACT_STRUCTURE_SYSTEM),
        HumanMessage(
            content=EXTRACT_STRUCTURE_USER.format(
                title=state.get("title", ""),
                company_name=state.get("company_name", ""),
                location=state.get("location", ""),
                raw_text=state.get("raw_text", ""),
            )
        ),
    ]
    try:
        response = await llm.ainvoke(messages)
        jd = JDStructure.model_validate_json(response_text(response))
        return {
            "jd_structured": jd.model_dump(),
            "skills_required": jd.skills_required,
        }
    except Exception as exc:
        log.warning("extract_structure_failed", extra={"error": str(exc)})
        return {
            "jd_structured": {},
            "skills_required": [],
            "error": str(exc),
        }


async def _compute_match_node(state: AnalyzerState) -> dict[str, Any]:
    """Compute quick match score comparing JD skills against resume."""
    resume_text = state.get("resume_text", "")
    if not resume_text or not state.get("jd_structured"):
        return {"match_score": 0.0}

    llm = get_llm().bind(**_JSON_MODE)
    messages = [
        SystemMessage(content=MATCH_SCORE_SYSTEM),
        HumanMessage(
            content=MATCH_SCORE_USER.format(
                jd_structured=json.dumps(state["jd_structured"], ensure_ascii=False),
                resume_text=resume_text[:4000],  # cap to avoid token overflow
            )
        ),
    ]
    try:
        response = await llm.ainvoke(messages)
        result = MatchScoreOutput.model_validate_json(response_text(response))
        return {"match_score": result.match_score}
    except Exception as exc:
        log.warning("compute_match_failed", extra={"error": str(exc)})
        return {"match_score": 0.0}


def _build_graph() -> StateGraph[AnalyzerState]:
    g: StateGraph[AnalyzerState] = StateGraph(AnalyzerState)
    g.add_node("fetch_resume", _fetch_resume_node)
    g.add_node("extract_structure", _extract_structure_node)
    g.add_node("compute_match", _compute_match_node)

    g.set_entry_point("fetch_resume")
    g.add_edge("fetch_resume", "extract_structure")
    g.add_edge("extract_structure", "compute_match")
    g.add_edge("compute_match", END)
    return g


analyzer_graph = _build_graph().compile()
