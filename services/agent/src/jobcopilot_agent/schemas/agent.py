import uuid
from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, Field

# ── Request schemas ──────────────────────────────────────────────────────────


class AnalyzeJobRequest(BaseModel):
    job_id: uuid.UUID
    url: str
    title: str
    company_name: str
    location: str = ""
    raw_text: str


class MatchResumeRequest(BaseModel):
    job_id: uuid.UUID


class PrepareInterviewRequest(BaseModel):
    job_id: uuid.UUID


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    # JD screenshots as data URLs (data:image/...;base64,...) — only meaningful
    # on the LAST user message; transcribed server-side before the ReAct run.
    images: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


# ── Response schemas ─────────────────────────────────────────────────────────


class JdStructured(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    employment_type: str = ""
    experience_years: int | None = None
    skills_required: list[str] = []
    skills_preferred: list[str] = []
    responsibilities: list[str] = []
    qualifications: list[str] = []
    salary_range: str | None = None


class AnalyzeJobResponse(BaseModel):
    analysis_id: uuid.UUID
    job_id: uuid.UUID
    jd_structured: JdStructured
    skills_required: list[str]
    match_score: float
    status: str


class ResumeSuggestions(BaseModel):
    match_score: float
    gap_analysis: dict[str, Any]
    suggestions: list[str]


class MatchResumeResponse(BaseModel):
    analysis_id: uuid.UUID
    job_id: uuid.UUID
    match_score: float
    resume_suggestions: ResumeSuggestions
    status: str


class InterviewQuestion(BaseModel):
    question: str
    category: str  # "behavioral" | "technical"
    reference_answer: str


class PrepareInterviewResponse(BaseModel):
    analysis_id: uuid.UUID
    job_id: uuid.UUID
    questions: list[InterviewQuestion]
    status: str


class AnalysisResponse(BaseModel):
    # The ORM attribute is `id` (shared UUIDPrimaryKeyMixin); accept both so
    # model_validate(orm_obj) works while the wire field stays `analysis_id`.
    analysis_id: uuid.UUID = Field(validation_alias=AliasChoices("analysis_id", "id"))
    job_id: uuid.UUID
    user_id: uuid.UUID
    jd_structured: dict[str, Any] | None
    skills_required: list[Any] | None
    match_score: float | None
    resume_suggestions: dict[str, Any] | None
    interview_questions: dict[str, Any] | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
