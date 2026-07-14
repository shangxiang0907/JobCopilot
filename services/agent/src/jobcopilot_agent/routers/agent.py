"""
/v1/agent/* — synchronous analysis endpoints.

POST /v1/agent/analyze    → AnalyzerGraph
POST /v1/agent/match      → ResumeGraph
POST /v1/agent/interview  → InterviewGraph
GET  /v1/agent/analyses/{job_id} → fetch stored analysis
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, status

from jobcopilot_agent.deps import CurrentUser, DbDep, LLMKeyDep
from jobcopilot_agent.repositories.analysis_repo import AnalysisRepository
from jobcopilot_agent.schemas.agent import (
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
from jobcopilot_agent.services.analysis import run_job_analysis
from jobcopilot_agent.services.interview import prepare_interview_questions
from jobcopilot_agent.services.matching import run_resume_match

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/agent", tags=["agent"])


@router.post(
    "/analyze",
    response_model=AnalyzeJobResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[LLMKeyDep],
)
async def analyze_job(
    req: AnalyzeJobRequest,
    user: CurrentUser,
    db: DbDep,
) -> AnalyzeJobResponse:
    """Run AnalyzerGraph on a job posting and persist the structured analysis."""
    outcome = await run_job_analysis(
        db,
        job_id=req.job_id,
        user_id=uuid.UUID(str(user["user_id"])),
        tenant_id=uuid.UUID(str(user["tenant_id"])),
        url=req.url,
        title=req.title,
        company_name=req.company_name,
        location=req.location,
        raw_text=req.raw_text,
    )

    return AnalyzeJobResponse(
        analysis_id=outcome.analysis_id,
        job_id=req.job_id,
        jd_structured=JdStructured(**outcome.jd_structured),
        skills_required=outcome.skills_required,
        match_score=outcome.match_score,
        status=outcome.status,
    )


@router.post(
    "/match",
    response_model=MatchResumeResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[LLMKeyDep],
)
async def match_resume(
    req: MatchResumeRequest,
    user: CurrentUser,
    db: DbDep,
) -> MatchResumeResponse:
    """Run ResumeGraph for detailed gap analysis and tailored suggestions."""
    outcome = await run_resume_match(
        db,
        job_id=req.job_id,
        user_id=uuid.UUID(str(user["user_id"])),
        tenant_id=uuid.UUID(str(user["tenant_id"])),
    )
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis found for this job. Run /analyze first.",
        )

    suggestions = ResumeSuggestions(
        match_score=outcome.match_score,
        gap_analysis=outcome.gap_analysis,
        suggestions=[s.get("action", "") for s in outcome.suggestions],
    )
    return MatchResumeResponse(
        analysis_id=outcome.analysis_id,
        job_id=req.job_id,
        match_score=outcome.match_score,
        resume_suggestions=suggestions,
        status="done",
    )


@router.post(
    "/interview",
    response_model=PrepareInterviewResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[LLMKeyDep],
)
async def prepare_interview(
    req: PrepareInterviewRequest,
    user: CurrentUser,
    db: DbDep,
) -> PrepareInterviewResponse:
    """Run InterviewGraph to generate behavioral + technical questions."""
    prep = await prepare_interview_questions(
        db,
        job_id=req.job_id,
        user_id=uuid.UUID(str(user["user_id"])),
        tenant_id=uuid.UUID(str(user["tenant_id"])),
    )
    if prep is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis found for this job. Run /analyze first.",
        )

    all_questions = [
        InterviewQuestion(category="behavioral", **q) for q in prep.behavioral_questions
    ] + [InterviewQuestion(category="technical", **q) for q in prep.technical_questions]

    return PrepareInterviewResponse(
        analysis_id=prep.analysis_id,
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
