"""
InterviewGraph — generates behavioral and technical interview questions.

Nodes:
  1. gen_behavioral  → LLM JSON → behavioral Q&A
  2. gen_technical   → LLM JSON → technical Q&A
"""

import json
import logging
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from jobcopilot_agent.prompts.interview import (
    BEHAVIORAL_SYSTEM,
    BEHAVIORAL_USER,
    TECHNICAL_SYSTEM,
    TECHNICAL_USER,
)
from jobcopilot_agent.services.llm import get_llm

log = logging.getLogger(__name__)

_JSON_MODE = {"response_format": {"type": "json_object"}}


class InterviewState(TypedDict):
    # Inputs
    job_id: str
    user_id: str
    tenant_id: str
    jd_structured: dict[str, Any]
    # Outputs
    behavioral_questions: list[dict[str, Any]]
    technical_questions: list[dict[str, Any]]
    error: str | None


def _jd_field(state: InterviewState, key: str, default: object = "") -> object:
    return state.get("jd_structured", {}).get(key, default)


async def _gen_behavioral_node(state: InterviewState) -> dict[str, Any]:
    llm = get_llm().bind(**_JSON_MODE)
    messages = [
        SystemMessage(content=BEHAVIORAL_SYSTEM),
        HumanMessage(
            content=BEHAVIORAL_USER.format(
                title=_jd_field(state, "title"),
                company=_jd_field(state, "company"),
                responsibilities=json.dumps(
                    _jd_field(state, "responsibilities", []), ensure_ascii=False
                ),
                skills_required=json.dumps(
                    _jd_field(state, "skills_required", []), ensure_ascii=False
                ),
            )
        ),
    ]
    try:
        response = await llm.ainvoke(messages)
        assert isinstance(response.content, str)
        result = json.loads(response.content)
        return {"behavioral_questions": result.get("questions", [])}
    except Exception as exc:
        log.warning("gen_behavioral_failed", extra={"error": str(exc)})
        return {"behavioral_questions": [], "error": str(exc)}


async def _gen_technical_node(state: InterviewState) -> dict[str, Any]:
    llm = get_llm().bind(**_JSON_MODE)
    messages = [
        SystemMessage(content=TECHNICAL_SYSTEM),
        HumanMessage(
            content=TECHNICAL_USER.format(
                title=_jd_field(state, "title"),
                company=_jd_field(state, "company"),
                skills_required=json.dumps(
                    _jd_field(state, "skills_required", []), ensure_ascii=False
                ),
                skills_preferred=json.dumps(
                    _jd_field(state, "skills_preferred", []), ensure_ascii=False
                ),
                experience_years=_jd_field(state, "experience_years") or "not specified",
            )
        ),
    ]
    try:
        response = await llm.ainvoke(messages)
        assert isinstance(response.content, str)
        result = json.loads(response.content)
        return {"technical_questions": result.get("questions", [])}
    except Exception as exc:
        log.warning("gen_technical_failed", extra={"error": str(exc)})
        return {"technical_questions": [], "error": str(exc)}


def _build_graph() -> StateGraph[InterviewState]:
    g: StateGraph[InterviewState] = StateGraph(InterviewState)
    g.add_node("gen_behavioral", _gen_behavioral_node)
    g.add_node("gen_technical", _gen_technical_node)
    g.set_entry_point("gen_behavioral")
    g.add_edge("gen_behavioral", "gen_technical")
    g.add_edge("gen_technical", END)
    return g


interview_graph = _build_graph().compile()
