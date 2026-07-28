"""Extract raw text and lightweight section structure from PDF / DOCX files.

Three outcomes are kept distinct on purpose, because the product's entire value
rests on this text being real:

    extraction succeeded with text  -> parse_status="ok"
    extraction succeeded, no text   -> parse_status="no_text_layer" (scanned
                                       image; legitimate, but the resume cannot
                                       feed any AI feature, so it is flagged and
                                       counted rather than passed off as content)
    extraction raised               -> ResumeParseError

This module used to return "" for all three. An unreadable upload then became
the user's default resume and every AI action either failed far from its cause
or, worse, scored jobs against an empty resume and produced fluent nonsense —
the failure mode CLAUDE.md calls the most expensive in this repo.
"""

from pathlib import Path
from typing import Any

from jobcopilot_shared.exceptions import ResumeParseError
from jobcopilot_shared.logging import get_logger
from jobcopilot_shared.metrics import record_degradation

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
    """Extract text from a stored resume file.

    Raises ResumeParseError when the file cannot be read at all — the caller
    must not persist a resume whose text never arrived.
    """
    path = Path(file_url)
    ext = path.suffix.lower()

    if ext == ".pdf":
        raw_text = _extract_pdf(path)
        method = "pypdf"
    elif ext in {".docx", ".doc"}:
        raw_text = _extract_docx(path)
        method = "python-docx"
    else:
        # Unreachable via the API (file_storage validates extensions first), so
        # arriving here means a new caller skipped validation.
        raise ResumeParseError(f"Unsupported resume format: {ext or 'unknown'}")

    if raw_text.strip():
        parse_status = "ok"
    else:
        # A PDF of scanned pages parses cleanly and legitimately yields nothing.
        # Continuing is correct — the user's file is stored and they can replace
        # it — but the resume is unusable for matching, so it must be visible in
        # the response and countable in production rather than silently empty.
        parse_status = "no_text_layer"
        logger.warning("resume_has_no_text_layer", path=str(path), parse_method=method)
        record_degradation(operation="resume_parse", reason="no_text_layer")

    return {
        "raw_text": raw_text,
        "sections": _detect_sections(raw_text),
        "word_count": len(raw_text.split()),
        "parse_method": method,
        "parse_status": parse_status,
    }


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        logger.error("pdf_parse_failed", path=str(path), error=str(exc))
        raise ResumeParseError(
            "Could not read this PDF. Try re-exporting it or uploading a DOCX."
        ) from exc
    return "\n".join(pages).strip()


def _extract_docx(path: Path) -> str:
    try:
        from docx import Document

        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    except Exception as exc:
        logger.error("docx_parse_failed", path=str(path), error=str(exc))
        raise ResumeParseError(
            "Could not read this document. Try re-saving it as PDF or DOCX."
        ) from exc
    return "\n".join(paragraphs).strip()


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
