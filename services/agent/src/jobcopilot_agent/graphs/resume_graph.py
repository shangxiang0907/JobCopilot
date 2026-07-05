"""
ResumeGraph — detailed gap analysis and tailored suggestions.

Nodes:
  1. gap_analysis  → LLM JSON → detailed gap + suggestions
"""

import json
import logging
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from jobcopilot_agent.graphs._content import response_text
from jobcopilot_agent.prompts.resume import GAP_ANALYSIS_SYSTEM, GAP_ANALYSIS_USER
from jobcopilot_agent.services.llm import get_llm

log = logging.getLogger(__name__)

_JSON_MODE = {"response_format": {"type": "json_object"}}


class ResumeState(TypedDict):
    # Inputs
    job_id: str
    user_id: str
    tenant_id: str
    jd_structured: dict[str, Any]
    resume_text: str
    # Outputs
    match_score: float
    gap_analysis: dict[str, Any]
    suggestions: list[dict[str, Any]]
    error: str | None


async def _gap_analysis_node(state: ResumeState) -> dict[str, Any]:
    """Run LLM gap analysis and generate tailored suggestions."""
    llm = get_llm().bind(**_JSON_MODE)
    messages = [
        SystemMessage(content=GAP_ANALYSIS_SYSTEM),
        HumanMessage(
            content=GAP_ANALYSIS_USER.format(
                jd_structured=json.dumps(state.get("jd_structured", {}), ensure_ascii=False),
                resume_text=state.get("resume_text", "")[:4000],
            )
        ),
    ]
    try:
        response = await llm.ainvoke(messages)
        result = json.loads(response_text(response))
        return {
            "match_score": float(result.get("match_score", 0)),
            "gap_analysis": {
                "hard_skills_gap": result.get("hard_skills_gap", []),
                "soft_skills_gap": result.get("soft_skills_gap", []),
                "experience_gap": result.get("experience_gap", ""),
                "education_gap": result.get("education_gap"),
                "strengths": result.get("strengths", []),
            },
            "suggestions": result.get("suggestions", []),
        }
    except Exception as exc:
        log.warning("gap_analysis_failed", extra={"error": str(exc)})
        return {
            "match_score": 0.0,
            "gap_analysis": {},
            "suggestions": [],
            "error": str(exc),
        }


def _build_graph() -> StateGraph[ResumeState]:
    g: StateGraph[ResumeState] = StateGraph(ResumeState)
    g.add_node("gap_analysis", _gap_analysis_node)
    g.set_entry_point("gap_analysis")
    g.add_edge("gap_analysis", END)
    return g


resume_graph = _build_graph().compile()
