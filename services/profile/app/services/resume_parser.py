"""Extract raw text and lightweight section structure from PDF / DOCX files."""

from pathlib import Path
from typing import Any

from jobcopilot_shared.logging import get_logger

logger = get_logger(__name__)

_SECTION_KEYWORDS = {
    "experience": ["experience", "work history", "employment", "职业经历", "工作经历"],
    "education": ["education", "academic", "学历", "教育背景"],
    "skills": ["skills", "technologies", "技能", "技术栈"],
    "summary": ["summary", "objective", "profile", "about", "个人简介"],
    "projects": ["projects", "项目经历"],
    "certifications": ["certifications", "certificates", "证书"],
}


def parse(file_url: str) -> dict[str, Any]:
    path = Path(file_url)
    ext = path.suffix.lower()

    if ext == ".pdf":
        raw_text = _extract_pdf(path)
        method = "pypdf"
    elif ext in {".docx", ".doc"}:
        raw_text = _extract_docx(path)
        method = "python-docx"
    else:
        raw_text = ""
        method = "unsupported"

    sections = _detect_sections(raw_text)
    return {
        "raw_text": raw_text,
        "sections": sections,
        "word_count": len(raw_text.split()),
        "parse_method": method,
    }


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()
    except Exception as exc:
        logger.warning("pdf_parse_failed", path=str(path), error=str(exc))
        return ""


def _extract_docx(path: Path) -> str:
    try:
        from docx import Document

        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs).strip()
    except Exception as exc:
        logger.warning("docx_parse_failed", path=str(path), error=str(exc))
        return ""


def _detect_sections(text: str) -> dict[str, list[str]]:
    """Return a rough mapping of section name → lines in that section."""
    lines = text.splitlines()
    sections: dict[str, list[str]] = {k: [] for k in _SECTION_KEYWORDS}
    current: str | None = None

    for line in lines:
        lower = line.lower().strip()
        matched = _match_section(lower)
        if matched:
            current = matched
        elif current:
            sections[current].append(line.strip())

    return {k: v for k, v in sections.items() if v}


def _match_section(lower_line: str) -> str | None:
    for section, keywords in _SECTION_KEYWORDS.items():
        if any(kw in lower_line for kw in keywords):
            return section
    return None
