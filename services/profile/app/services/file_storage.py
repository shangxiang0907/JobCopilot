"""Local-filesystem file storage. Replace with S3 adapter in production."""

import uuid
from pathlib import Path

import aiofiles
from fastapi import UploadFile
from jobcopilot_shared.exceptions import ValidationError
from jobcopilot_shared.logging import get_logger

from app.config import settings

logger = get_logger(__name__)

_ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}
_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}
_MAX_BYTES = settings.max_resume_size_mb * 1024 * 1024


async def save_resume(file: UploadFile, user_id: uuid.UUID) -> tuple[str, str]:
    """Validate, persist and return (file_name, file_url)."""
    _validate(file)

    ext = Path(file.filename or "resume").suffix.lower()
    safe_name = f"{uuid.uuid4()}{ext}"
    user_dir = Path(settings.resume_storage_path) / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / safe_name

    content = await file.read()
    if len(content) > _MAX_BYTES:
        raise ValidationError(
            f"File exceeds maximum size of {settings.max_resume_size_mb} MB"
        )

    async with aiofiles.open(dest, "wb") as f:
        await f.write(content)

    logger.info("resume_saved", user_id=str(user_id), path=str(dest))
    return file.filename or safe_name, str(dest)


async def delete_resume(file_url: str) -> None:
    import aiofiles.os

    path = Path(file_url)
    if await aiofiles.os.path.exists(str(path)):
        await aiofiles.os.remove(str(path))
        logger.info("resume_deleted", path=str(path))


def _validate(file: UploadFile) -> None:
    if file.content_type and file.content_type not in _ALLOWED_MIME:
        raise ValidationError(f"Unsupported file type: {file.content_type}")
    ext = Path(file.filename or "").suffix.lower()
    if ext and ext not in _ALLOWED_EXTENSIONS:
        raise ValidationError(f"Unsupported file extension: {ext}")
