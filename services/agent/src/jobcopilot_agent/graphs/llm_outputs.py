"""Pydantic schemas for LLM JSON outputs — one model per prompt contract.

Each model mirrors the JSON schema stated in the corresponding prompt in
`jobcopilot_agent/prompts/`; change them together. Graph nodes validate the
raw LLM response with `model_validate_json` instead of bare `json.loads`, so
a malformed or drifted response fails loudly into the node's error path
instead of leaking wrong shapes downstream.

Missing optional fields fall back to safe defaults (the LLM omitting a list
is tolerable); wrong types and out-of-range scores are hard failures.
"""

from pydantic import BaseModel, ConfigDict, Field


class JDStructure(BaseModel):
    """EXTRACT_STRUCTURE_SYSTEM output (prompts/analyzer.py)."""

    # Extra keys the LLM volunteers are kept in jd_structured downstream.
    model_config = ConfigDict(extra="allow")

    title: str = ""
    company: str = ""
    location: str = ""
    employment_type: str = ""
    experience_years: float | None = None
    skills_required: list[str] = Field(default_factory=list)
    skills_preferred: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)
    salary_range: str | None = None


class MatchScoreOutput(BaseModel):
    """MATCH_SCORE_SYSTEM output (prompts/analyzer.py)."""

    match_score: float = Field(ge=0, le=100)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    summary: str = ""


class ResumeSuggestion(BaseModel):
    """One entry of GAP_ANALYSIS_SYSTEM's suggestions[] (prompts/resume.py)."""

    section: str
    action: str
    example: str = ""


class GapAnalysisOutput(BaseModel):
    """GAP_ANALYSIS_SYSTEM output (prompts/resume.py)."""

    match_score: float = Field(ge=0, le=100)
    hard_skills_gap: list[str] = Field(default_factory=list)
    soft_skills_gap: list[str] = Field(default_factory=list)
    experience_gap: str = ""
    education_gap: str | None = None
    strengths: list[str] = Field(default_factory=list)
    suggestions: list[ResumeSuggestion] = Field(default_factory=list)


class BehavioralQuestion(BaseModel):
    """One entry of BEHAVIORAL_SYSTEM's questions[] (prompts/interview.py)."""

    question: str
    intent: str = ""
    reference_answer: str = ""


class BehavioralQuestionsOutput(BaseModel):
    questions: list[BehavioralQuestion]


class TechnicalQuestion(BaseModel):
    """One entry of TECHNICAL_SYSTEM's questions[] (prompts/interview.py)."""

    question: str
    difficulty: str = ""
    topic: str = ""
    reference_answer: str = ""


class TechnicalQuestionsOutput(BaseModel):
    questions: list[TechnicalQuestion]
