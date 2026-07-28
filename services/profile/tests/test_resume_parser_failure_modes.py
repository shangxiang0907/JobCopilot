"""Parse failure, an empty text layer and real content must stay distinguishable.

The parser used to return "" for all three. The consequence was not a crash but
something worse: an unreadable upload became the user's default resume, and the
analyzer scored jobs against an empty string — producing fluent, confident,
entirely wrong output with nothing in the logs. See CLAUDE.md
"Error Handling — No Silent Degradation".
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from jobcopilot_profile.services import resume_parser
from jobcopilot_shared.exceptions import ResumeParseError


def _pdf_reader(pages_text: list[str]) -> MagicMock:
    reader = MagicMock()
    reader.pages = [MagicMock(extract_text=MagicMock(return_value=t)) for t in pages_text]
    return reader


def test_real_content_parses_as_ok() -> None:
    with patch("pypdf.PdfReader", return_value=_pdf_reader(["Senior Python engineer"])):
        result = resume_parser.parse("/data/resumes/cv.pdf")

    assert result["parse_status"] == "ok"
    assert result["raw_text"] == "Senior Python engineer"
    assert result["word_count"] == 3


def test_corrupt_pdf_raises_instead_of_returning_empty_text() -> None:
    """The upload must fail at its cause, not silently three features later."""
    with patch("pypdf.PdfReader", side_effect=ValueError("EOF marker not found")):
        with pytest.raises(ResumeParseError, match="Could not read this PDF"):
            resume_parser.parse("/data/resumes/cv.pdf")


def test_corrupt_docx_raises() -> None:
    with patch("docx.Document", side_effect=KeyError("word/document.xml")):
        with pytest.raises(ResumeParseError, match="Could not read this document"):
            resume_parser.parse("/data/resumes/cv.docx")


def test_scanned_pdf_is_flagged_not_treated_as_content() -> None:
    """A page image parses cleanly and yields nothing — legitimate, but unusable."""
    with (
        patch("pypdf.PdfReader", return_value=_pdf_reader(["", "   "])),
        patch("jobcopilot_profile.services.resume_parser.record_degradation") as metric,
    ):
        result = resume_parser.parse("/data/resumes/scan.pdf")

    assert result["parse_status"] == "no_text_layer"
    assert result["raw_text"] == ""
    # A degradation with no metric is invisible in production.
    metric.assert_called_once_with(operation="resume_parse", reason="no_text_layer")


def test_unsupported_extension_raises_rather_than_returning_a_shell() -> None:
    with pytest.raises(ResumeParseError, match="Unsupported resume format"):
        resume_parser.parse("/data/resumes/notes.txt")


def test_sections_are_detected_from_real_content() -> None:
    text = "Experience\nBuilt a platform\nSkills\nPython, SQL"
    with patch("pypdf.PdfReader", return_value=_pdf_reader([text])):
        result = resume_parser.parse("/data/resumes/cv.pdf")

    assert result["sections"]["experience"] == ["Built a platform"]
    assert result["sections"]["skills"] == ["Python, SQL"]


@pytest.mark.asyncio
async def test_rejected_upload_deletes_the_orphaned_file() -> None:
    """A parse failure must not leave a file that no DB row will ever reference.

    save_resume writes to disk before parsing, so without this cleanup every
    unreadable upload leaks a file nothing can ever attribute to a user.
    """
    from unittest.mock import AsyncMock

    from jobcopilot_profile.routers.resumes import upload_resume

    stored_path = "/data/resumes/user-1/abc.pdf"
    with (
        patch(
            "jobcopilot_profile.services.file_storage.save_resume",
            new_callable=AsyncMock,
            return_value=("cv.pdf", stored_path),
        ),
        patch(
            "jobcopilot_profile.services.resume_parser.parse",
            side_effect=ResumeParseError("Could not read this PDF."),
        ),
        patch(
            "jobcopilot_profile.services.file_storage.delete_resume", new_callable=AsyncMock
        ) as delete,
    ):
        with pytest.raises(ResumeParseError):
            await upload_resume(
                file=MagicMock(),
                background_tasks=MagicMock(),
                session=AsyncMock(),
                tenant_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
            )

    delete.assert_awaited_once_with(stored_path)
