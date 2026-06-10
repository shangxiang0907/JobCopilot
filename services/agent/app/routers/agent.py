"""
/v1/agent/* — synchronous analysis endpoints.

POST /v1/agent/analyze    → AnalyzerGraph
POST /v1/agent/match      → ResumeGraph
POST /v1/agent/interview  → InterviewGraph
GET  /v1/agent/analyses/{job_id} → fetch stored analysis
"""

import logging
import uuid

import httpx
from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.deps import CurrentUser, DbDep
from app.graphs.analyzer_graph import AnalyzerState, analyzer_graph
from app.graphs.interview_graph import InterviewState, interview_graph
from app.graphs.resume_graph import ResumeState, resume_graph
from app.repositories.analysis_repo import AnalysisRepository
from app.schemas.agent import (
    AnalysisResponse,
    AnalyzeJobRequest,
    AnalyzeJobResponse,
    InterviewQuestion,
    JdStructured,
    MatchResumeRequest,
    MatchResumeResponse,
    PrepareInterviewRequest,
    PrepareInterviewResponse,
    ResumeSuggestions,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/agent", tags=["agent"])


@router.post("/analyze", response_model=AnalyzeJobResponse, status_code=status.HTTP_200_OK)
async def analyze_job(
    req: AnalyzeJobRequest,
    user: CurrentUser,
    db: DbDep,
) -> AnalyzeJobResponse:
    """Run AnalyzerGraph on a job posting and persist the structured analysis."""
    state: AnalyzerState = {
        "job_id": str(req.job_id),
        "user_id": str(user["user_id"]),
        "tenant_id": str(user["tenant_id"]),
        "url": req.url,
        "title": req.title,
        "company_name": req.company_name,
        "location": req.location,
        "raw_text": req.raw_text,
        "resume_text": "",
        "jd_structured": {},
        "skills_required": [],
        "match_score": 0.0,
        "error": None,
    }
    result = await analyzer_graph.ainvoke(state)

    repo = AnalysisRepository(db)
    async with db.begin():
        analysis = await repo.get_or_create(req.job_id, user["user_id"], user["tenant_id"])
        await repo.update_analysis(
            analysis,
            jd_structured=result.get("jd_structured"),
            skills_required=result.get("skills_required"),
            match_score=result.get("match_score"),
            status="done" if not result.get("error") else "error",
            error_message=result.get("error"),
        )

    return AnalyzeJobResponse(
        analysis_id=analysis.id,
        job_id=req.job_id,
        jd_structured=JdStructured(**result.get("jd_structured", {})),
        skills_required=result.get("skills_required", []),
        match_score=result.get("match_score", 0.0),
        status=analysis.status,
    )


@router.post("/match", response_model=MatchResumeResponse, status_code=status.HTTP_200_OK)
async def match_resume(
    req: MatchResumeRequest,
    user: CurrentUser,
    db: DbDep,
) -> MatchResumeResponse:
    """Run ResumeGraph for detailed gap analysis and tailored suggestions."""
    # Fetch stored JD structure
    repo = AnalysisRepository(db)
    analysis = await repo.get_by_job_user(req.job_id, user["user_id"], user["tenant_id"])
    if not analysis or not analysis.jd_structured:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis found for this job. Run /analyze first.",
        )

    # Fetch resume text from Profile Service
    resume_text = ""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.profile_service_url}/internal/profiles/{user['user_id']}"
            )
        if resp.status_code == 200:
            resume_text = resp.json().get("active_resume_text") or ""
    except Exception as exc:
        log.warning("profile_fetch_failed", extra={"error": str(exc)})

    state: ResumeState = {
        "job_id": str(req.job_id),
        "user_id": str(user["user_id"]),
        "tenant_id": str(user["tenant_id"]),
        "jd_structured": analysis.jd_structured,
        "resume_text": resume_text,
        "match_score": 0.0,
        "gap_analysis": {},
        "suggestions": [],
        "error": None,
    }
    result = await resume_graph.ainvoke(state)

    async with db.begin():
        await repo.update_analysis(
            analysis,
            match_score=result.get("match_score"),
            resume_suggestions={
                "gap_analysis": result.get("gap_analysis"),
                "suggestions": result.get("suggestions"),
            },
            status="done",
        )

    suggestions = ResumeSuggestions(
        match_score=result.get("match_score", 0.0),
        gap_analysis=result.get("gap_analysis", {}),
        suggestions=[s.get("action", "") for s in result.get("suggestions", [])],
    )
    return MatchResumeResponse(
        analysis_id=analysis.id,
        job_id=req.job_id,
        match_score=result.get("match_score", 0.0),
        resume_suggestions=suggestions,
        status="done",
    )


@router.post("/interview", response_model=PrepareInterviewResponse, status_code=status.HTTP_200_OK)
async def prepare_interview(
    req: PrepareInterviewRequest,
    user: CurrentUser,
    db: DbDep,
) -> PrepareInterviewResponse:
    """Run InterviewGraph to generate behavioral + technical questions."""
    repo = AnalysisRepository(db)
    analysis = await repo.get_by_job_user(req.job_id, user["user_id"], user["tenant_id"])
    if not analysis or not analysis.jd_structured:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis found for this job. Run /analyze first.",
        )

    state: InterviewState = {
        "job_id": str(req.job_id),
        "user_id": str(user["user_id"]),
        "tenant_id": str(user["tenant_id"]),
        "jd_structured": analysis.jd_structured,
        "behavioral_questions": [],
        "technical_questions": [],
        "error": None,
    }
    result = await interview_graph.ainvoke(state)

    all_questions = [
        InterviewQuestion(category="behavioral", **q)
        for q in result.get("behavioral_questions", [])
    ] + [
        InterviewQuestion(category="technical", **q)
        for q in result.get("technical_questions", [])
    ]

    interview_data = {
        "behavioral": result.get("behavioral_questions", []),
        "technical": result.get("technical_questions", []),
    }
    async with db.begin():
        await repo.update_analysis(analysis, interview_questions=interview_data, status="done")

    return PrepareInterviewResponse(
        analysis_id=analysis.id,
        job_id=req.job_id,
        questions=all_questions,
        status="done",
    )


@router.get("/analyses/{job_id}", response_model=AnalysisResponse)
async def get_analysis(
    job_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
) -> AnalysisResponse:
    """Retrieve stored analysis results for a job."""
    repo = AnalysisRepository(db)
    analysis = await repo.get_by_job_user(job_id, user["user_id"], user["tenant_id"])
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return AnalysisResponse.model_validate(analysis)
