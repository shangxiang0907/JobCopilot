import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, UploadFile, status
from jobcopilot_shared.exceptions import ResumeParseError
from jobcopilot_shared.logging import get_logger
from jobcopilot_shared.metrics import record_degradation
from jobcopilot_shared.schemas.common import PaginatedResponse

from jobcopilot_profile.deps import SessionDep, TenantIdDep, UserIdDep
from jobcopilot_profile.repositories.resume_repo import ResumeRepository
from jobcopilot_profile.schemas.resume import ResumeResponse, ResumeSetDefault, ResumeUpdate
from jobcopilot_profile.services import embedding, file_storage, resume_parser

logger = get_logger(__name__)
router = APIRouter(prefix="/v1/resumes", tags=["resumes"])


@router.get("", response_model=PaginatedResponse[ResumeResponse])
async def list_resumes(
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> PaginatedResponse[ResumeResponse]:
    """All /v1 collection endpoints return PaginatedResponse — see CLAUDE.md."""
    repo = ResumeRepository(session)
    resumes = await repo.list(user_id)
    items = [ResumeResponse.model_validate(r) for r in resumes]
    return PaginatedResponse(
        items=items, total=len(items), page=1, size=max(len(items), 1), has_next=False
    )


@router.post("", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> ResumeResponse:
    file_name, file_url = await file_storage.save_resume(file, user_id)
    try:
        parsed = await asyncio.get_event_loop().run_in_executor(None, resume_parser.parse, file_url)
    except ResumeParseError:
        # The file is on disk but will have no row referencing it. Delete it now
        # or every rejected upload leaks a file that nothing can ever clean up.
        await file_storage.delete_resume(file_url)
        raise

    repo = ResumeRepository(session)
    resume = await repo.create(user_id, file_name, file_url, parsed)

    # Resolve the key now (needs the request's DB session); the background task
    # must not touch the session after the response is sent.
    embedding_api_key = await embedding.resolve_embedding_api_key(session, user_id)
    await session.commit()
    background_tasks.add_task(
        embedding.embed_and_upsert,
        resume.resume_id,
        user_id,
        parsed.get("raw_text", ""),
        embedding_api_key,
    )

    logger.info("resume_uploaded", user_id=str(user_id), resume_id=str(resume.resume_id))
    return ResumeResponse.model_validate(resume)


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: uuid.UUID,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> ResumeResponse:
    repo = ResumeRepository(session)
    resume = await repo.get(user_id, resume_id)
    return ResumeResponse.model_validate(resume)


@router.patch("/{resume_id}/default", response_model=ResumeResponse)
async def set_default_resume(
    resume_id: uuid.UUID,
    body: ResumeSetDefault,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> ResumeResponse:
    """Choose the resume used when nothing more specific is given (PRD v0.3).

    Changing the default never rewrites existing applications: each one records
    its own resume_id at the time it was created.
    """
    repo = ResumeRepository(session)
    if body.is_default:
        resume = await repo.set_default(user_id, resume_id)
    else:
        resume = await repo.get(user_id, resume_id)
        resume.is_default = False
    await session.commit()
    return ResumeResponse.model_validate(resume)


@router.patch("/{resume_id}", response_model=ResumeResponse)
async def update_resume(
    resume_id: uuid.UUID,
    body: ResumeUpdate,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> ResumeResponse:
    """Edit the user-supplied label/notes. The file itself is immutable."""
    repo = ResumeRepository(session)
    resume = await repo.update_metadata(user_id, resume_id, body.label, body.notes)
    await session.commit()
    return ResumeResponse.model_validate(resume)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> None:
    repo = ResumeRepository(session)
    # Deleting the default deliberately does NOT promote another resume: the
    # default is an explicit user choice and picking a replacement for them
    # would silently change which resume future AI actions read (owner decision,
    # PRD v0.3). The user is left with no default on purpose — the /profile page
    # surfaces that state and every AI action fail-fasts meanwhile, so it is
    # loud rather than silent. Counted because "user has resumes but no default"
    # is otherwise invisible in production.
    was_default = (await repo.get(user_id, resume_id)).is_default
    file_url = await repo.delete(user_id, resume_id)
    await session.commit()
    background_tasks.add_task(file_storage.delete_resume, file_url)
    background_tasks.add_task(embedding.delete_embedding, resume_id)
    logger.info(
        "resume_deleted",
        user_id=str(user_id),
        resume_id=str(resume_id),
        was_default=was_default,
    )
    if was_default:
        record_degradation(operation="resume_delete", reason="default_resume_removed")
        logger.warning("default_resume_deleted", user_id=str(user_id))
