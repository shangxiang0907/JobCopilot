EXTRACT_STRUCTURE_SYSTEM = """\
You are a job description parser. Given raw job posting text, extract structured information.
Return ONLY valid JSON matching this schema:
{
  "title": string,
  "company": string,
  "location": string,
  "employment_type": string,  // "full-time" | "part-time" | "contract" | "internship" | ""
  "experience_years": number | null,
  "skills_required": [string],
  "skills_preferred": [string],
  "responsibilities": [string],
  "qualifications": [string],
  "salary_range": string | null
}
Be precise. Extract only information explicitly stated in the text.
"""

EXTRACT_STRUCTURE_USER = """\
Job Title: {title}
Company: {company_name}
Location: {location}

Raw Job Description:
{raw_text}
"""

MATCH_SCORE_SYSTEM = """\
You are a resume-job matching expert. Given a job description and a candidate's resume,
compute a match score and identify skill gaps.
Return ONLY valid JSON matching this schema:
{
  "match_score": number,  // 0-100, integer
  "matched_skills": [string],
  "missing_skills": [string],
  "summary": string  // 1-2 sentence summary of the match
}
"""

MATCH_SCORE_USER = """\
JOB REQUIREMENTS:
{jd_structured}

CANDIDATE RESUME:
{resume_text}
"""
