"""Internal endpoint — Kong blocks external access via /internal/ path prefix."""

from fastapi import APIRouter, status

from jobcopilot_notification.deps import SessionDep
from jobcopilot_notification.schemas.notification import InternalNotifyRequest
from jobcopilot_notification.services.dispatcher import dispatch

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/notify", status_code=status.HTTP_202_ACCEPTED)
async def internal_notify(
    payload: InternalNotifyRequest,
    session: SessionDep,
) -> dict[str, int]:
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
    await session.commit()
    return {"dispatched": len(notifications)}
