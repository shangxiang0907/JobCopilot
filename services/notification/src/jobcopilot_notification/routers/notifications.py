import uuid

from fastapi import APIRouter, HTTPException, Query, status

from jobcopilot_notification.deps import SessionDep, TenantIdDep, UserIdDep
from jobcopilot_notification.repositories.notification_repo import NotificationRepository
from jobcopilot_notification.schemas.notification import (
    NotificationListResponse,
    NotificationOut,
    PreferenceOut,
    PreferenceUpdate,
)

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> NotificationListResponse:
    repo = NotificationRepository(session)
    items, total = await repo.list_for_user(
        tenant_id, user_id, channel="in_app", page=page, page_size=page_size
    )
    return NotificationListResponse(
        items=[NotificationOut.model_validate(n) for n in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: uuid.UUID,
    session: SessionDep,
    user_id: UserIdDep,
) -> NotificationOut:
    repo = NotificationRepository(session)
    n = await repo.mark_read(notification_id, user_id)
    if n is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return NotificationOut.model_validate(n)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: uuid.UUID,
    session: SessionDep,
    user_id: UserIdDep,
) -> None:
    repo = NotificationRepository(session)
    deleted = await repo.delete(notification_id, user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")


@router.get("/preferences", response_model=PreferenceOut)
async def get_preferences(
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> PreferenceOut:
    repo = NotificationRepository(session)
    pref = await repo.get_preference(user_id)
    if pref is None:
        pref = await repo.upsert_preference(tenant_id=tenant_id, user_id=user_id)
    return PreferenceOut.model_validate(pref)


@router.put("/preferences", response_model=PreferenceOut)
async def update_preferences(
    payload: PreferenceUpdate,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> PreferenceOut:
    updates: dict[str, object] = {}
    if payload.in_app_enabled is not None:
        updates["in_app_enabled"] = payload.in_app_enabled
    if payload.email_enabled is not None:
        updates["email_enabled"] = payload.email_enabled
    if payload.email_address is not None:
        updates["email_address"] = payload.email_address

    repo = NotificationRepository(session)
    pref = await repo.upsert_preference(tenant_id=tenant_id, user_id=user_id, **updates)
    return PreferenceOut.model_validate(pref)
