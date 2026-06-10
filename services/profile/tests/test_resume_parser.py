"""Unit tests for resume_parser — no filesystem or network required."""

from app.services.resume_parser import _detect_sections, _match_section


def test_match_section_experience() -> None:
    assert _match_section("work experience") == "experience"
    assert _match_section("employment history") == "experience"
    assert _match_section("工作经历") == "experience"


def test_match_section_education() -> None:
    assert _match_section("education") == "education"
    assert _match_section("academic background") == "education"
    assert _match_section("教育背景") == "education"


def test_match_section_skills() -> None:
    assert _match_section("skills") == "skills"
    assert _match_section("technologies") == "skills"
    assert _match_section("技能") == "skills"


def test_match_section_returns_none_for_unknown() -> None:
    assert _match_section("references") is None
    assert _match_section("john doe") is None
    assert _match_section("") is None


def test_detect_sections_extracts_experience_lines() -> None:
    text = """John Doe
Work Experience
Software Engineer at Acme Corp 2022-2024
Led backend team of 5 engineers
Education
B.S. Computer Science, MIT 2022
Skills
Python, FastAPI, PostgreSQL"""

    sections = _detect_sections(text)
    assert "experience" in sections
    assert any("Acme" in line for line in sections["experience"])
    assert "education" in sections
    assert "skills" in sections


def test_detect_sections_empty_text() -> None:
    sections = _detect_sections("")
    assert sections == {}


def test_detect_sections_no_known_headers() -> None:
    text = "Just some text\nwith no section headers at all"
    sections = _detect_sections(text)
    assert sections == {}
