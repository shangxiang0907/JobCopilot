"""Internal endpoint — Kong blocks external access via /internal/ path prefix."""

from fastapi import APIRouter, status

from app.deps import SessionDep
from app.schemas.notification import InternalNotifyRequest
from app.services.dispatcher import dispatch

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/notify", status_code=status.HTTP_202_ACCEPTED)
async def internal_notify(
    payload: InternalNotifyRequest,
    session: SessionDep,
) -> dict:
    notifications = await dispatch(
        session,
        tenant_id=payload.tenant_id,
        user_id=payload.user_id,
        type=payload.type,
        title=payload.title,
        body=payload.body,
        channels=payload.channels,
        metadata=payload.metadata,
    )
    return {"dispatched": len(notifications)}
