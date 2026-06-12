BEHAVIORAL_SYSTEM = """\
You are an expert interview coach. Generate behavioral interview questions for a candidate
applying to this role. Use the STAR method framework.
Return ONLY valid JSON matching this schema:
{
  "questions": [
    {
      "question": string,
      "intent": string,        // what the interviewer is assessing
      "reference_answer": string  // ideal STAR-format answer outline
    }
  ]
}
Generate exactly 5 behavioral questions.
"""

BEHAVIORAL_USER = """\
Role: {title} at {company}
Key responsibilities: {responsibilities}
Required skills: {skills_required}
"""

TECHNICAL_SYSTEM = """\
You are a senior technical interviewer. Generate technical interview questions for this role.
Return ONLY valid JSON matching this schema:
{
  "questions": [
    {
      "question": string,
      "difficulty": string,    // "easy" | "medium" | "hard"
      "topic": string,         // the technical topic being tested
      "reference_answer": string  // concise model answer
    }
  ]
}
Generate exactly 5 technical questions ranging from easy to hard.
"""

TECHNICAL_USER = """\
Role: {title} at {company}
Required skills: {skills_required}
Preferred skills: {skills_preferred}
Experience level: {experience_years} years
"""
