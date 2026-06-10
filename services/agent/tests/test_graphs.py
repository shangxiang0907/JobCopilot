"""Unit tests for LangGraph graphs — LLM calls are mocked."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.graphs.analyzer_graph import AnalyzerState, analyzer_graph
from app.graphs.interview_graph import InterviewState, interview_graph
from app.graphs.resume_graph import ResumeState, resume_graph


def _make_llm_response(content: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = json.dumps(content)
    return msg


# ── AnalyzerGraph ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyzer_graph_extracts_structure():
    jd = {
        "title": "Senior Python Engineer",
        "company": "Acme Corp",
        "location": "Remote",
        "employment_type": "full-time",
        "experience_years": 5,
        "skills_required": ["Python", "FastAPI", "PostgreSQL"],
        "skills_preferred": ["Kubernetes"],
        "responsibilities": ["Build APIs"],
        "qualifications": ["BS Computer Science"],
        "salary_range": None,
    }
    match = {
        "match_score": 82, "matched_skills": ["Python"], "missing_skills": [], "summary": "Good fit"
    }

    with (
        patch("app.graphs.analyzer_graph.get_llm") as mock_get_llm,
        patch("app.graphs.analyzer_graph.httpx.AsyncClient") as mock_client_cls,
    ):
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(
            side_effect=[_make_llm_response(jd), _make_llm_response(match)]
        )
        mock_get_llm.return_value = llm

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"active_resume_text": "Experienced Python developer"}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        state: AnalyzerState = {
            "job_id": "job-1",
            "user_id": "user-1",
            "tenant_id": "tenant-1",
            "url": "https://linkedin.com/jobs/1",
            "title": "Senior Python Engineer",
            "company_name": "Acme Corp",
            "location": "Remote",
            "raw_text": "We are looking for a Senior Python Engineer...",
            "resume_text": "",
            "jd_structured": {},
            "skills_required": [],
            "match_score": 0.0,
            "error": None,
        }
        result = await analyzer_graph.ainvoke(state)

    assert result["jd_structured"]["title"] == "Senior Python Engineer"
    assert "Python" in result["skills_required"]
    assert result["match_score"] == 82.0


@pytest.mark.asyncio
async def test_analyzer_graph_handles_missing_resume():
    jd = {"title": "Engineer", "company": "Corp", "location": "", "employment_type": "",
          "experience_years": None, "skills_required": ["Python"], "skills_preferred": [],
          "responsibilities": [], "qualifications": [], "salary_range": None}

    with (
        patch("app.graphs.analyzer_graph.get_llm") as mock_get_llm,
        patch("app.graphs.analyzer_graph.httpx.AsyncClient") as mock_client_cls,
    ):
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(return_value=_make_llm_response(jd))
        mock_get_llm.return_value = llm

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        state: AnalyzerState = {
            "job_id": "job-2", "user_id": "user-2", "tenant_id": "tenant-1",
            "url": "https://linkedin.com/jobs/2", "title": "Engineer",
            "company_name": "Corp", "location": "", "raw_text": "Job desc",
            "resume_text": "", "jd_structured": {}, "skills_required": [],
            "match_score": 0.0, "error": None,
        }
        result = await analyzer_graph.ainvoke(state)

    # No resume → match_score stays 0
    assert result["match_score"] == 0.0
    assert result["jd_structured"]["title"] == "Engineer"


# ── ResumeGraph ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resume_graph_gap_analysis():
    analysis_result = {
        "match_score": 75,
        "hard_skills_gap": ["Kubernetes"],
        "soft_skills_gap": [],
        "experience_gap": "Candidate has 3 years, role requires 5",
        "education_gap": None,
        "strengths": ["Python", "FastAPI"],
        "suggestions": [
            {
                "section": "Skills",
                "action": "Add Kubernetes experience",
                "example": "Managed K8s cluster",
            }
        ],
    }

    with patch("app.graphs.resume_graph.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(return_value=_make_llm_response(analysis_result))
        mock_get_llm.return_value = llm

        state: ResumeState = {
            "job_id": "job-1", "user_id": "user-1", "tenant_id": "tenant-1",
            "jd_structured": {
                "title": "Senior Engineer", "skills_required": ["Python", "Kubernetes"]
            },
            "resume_text": "Python developer with 3 years experience",
            "match_score": 0.0, "gap_analysis": {}, "suggestions": [], "error": None,
        }
        result = await resume_graph.ainvoke(state)

    assert result["match_score"] == 75.0
    assert "Kubernetes" in result["gap_analysis"]["hard_skills_gap"]
    assert len(result["suggestions"]) == 1


# ── InterviewGraph ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_interview_graph_generates_questions():
    behavioral = {
        "questions": [
            {
                "question": "Tell me about a challenge",
                "intent": "problem solving",
                "reference_answer": "Use STAR",
            }
        ] * 5
    }
    technical = {
        "questions": [
            {
                "question": "Explain asyncio",
                "difficulty": "medium",
                "topic": "Python async",
                "reference_answer": "Event loop...",
            }
        ] * 5
    }

    with patch("app.graphs.interview_graph.get_llm") as mock_get_llm:
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(side_effect=[
            _make_llm_response(behavioral),
            _make_llm_response(technical),
        ])
        mock_get_llm.return_value = llm

        state: InterviewState = {
            "job_id": "job-1", "user_id": "user-1", "tenant_id": "tenant-1",
            "jd_structured": {
                "title": "Python Engineer", "company": "Acme",
                "skills_required": ["Python", "asyncio"],
                "skills_preferred": ["FastAPI"],
                "responsibilities": ["Build services"],
                "experience_years": 3,
            },
            "behavioral_questions": [], "technical_questions": [], "error": None,
        }
        result = await interview_graph.ainvoke(state)

    assert len(result["behavioral_questions"]) == 5
    assert len(result["technical_questions"]) == 5
    assert result["technical_questions"][0]["topic"] == "Python async"
