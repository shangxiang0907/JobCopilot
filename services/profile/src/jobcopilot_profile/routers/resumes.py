import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, UploadFile, status
from jobcopilot_shared.logging import get_logger

from jobcopilot_profile.deps import SessionDep, TenantIdDep, UserIdDep
from jobcopilot_profile.repositories.resume_repo import ResumeRepository
from jobcopilot_profile.schemas.resume import ResumeActivate, ResumeResponse
from jobcopilot_profile.services import embedding, file_storage, resume_parser

logger = get_logger(__name__)
router = APIRouter(prefix="/v1/resumes", tags=["resumes"])


@router.get("", response_model=list[ResumeResponse])
async def list_resumes(
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> list[ResumeResponse]:
    repo = ResumeRepository(session)
    resumes = await repo.list(user_id)
    return [ResumeResponse.model_validate(r) for r in resumes]


@router.post("", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> ResumeResponse:
    file_name, file_url = await file_storage.save_resume(file, user_id)
    parsed = await asyncio.get_event_loop().run_in_executor(None, resume_parser.parse, file_url)

    repo = ResumeRepository(session)
    resume = await repo.create(user_id, file_name, file_url, parsed)

    background_tasks.add_task(
        embedding.embed_and_upsert,
        resume.resume_id,
        user_id,
        parsed.get("raw_text", ""),
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


@router.patch("/{resume_id}/activate", response_model=ResumeResponse)
async def activate_resume(
    resume_id: uuid.UUID,
    body: ResumeActivate,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> ResumeResponse:
    repo = ResumeRepository(session)
    if body.is_active:
        resume = await repo.set_active(user_id, resume_id)
    else:
        resume = await repo.get(user_id, resume_id)
        resume.is_active = False
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
    file_url = await repo.delete(user_id, resume_id)
    background_tasks.add_task(file_storage.delete_resume, file_url)
    background_tasks.add_task(embedding.delete_embedding, resume_id)
    logger.info("resume_deleted", user_id=str(user_id), resume_id=str(resume_id))
