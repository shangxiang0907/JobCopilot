import uuid

from fastapi import APIRouter, HTTPException, Query, status
from jobcopilot_shared.crypto import encrypt as _encrypt

from app.config import settings
from app.deps import SessionDep, TenantIdDep, UserIdDep
from app.repositories.notification_repo import NotificationRepository
from app.schemas.notification import (
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
    return PreferenceOut(
        id=pref.id,
        in_app_enabled=pref.in_app_enabled,
        email_enabled=pref.email_enabled,
        email_address=pref.email_address,
        wechat_configured=pref.wechat_webhook_enc is not None,
        dingtalk_configured=pref.dingtalk_webhook_enc is not None,
        created_at=pref.created_at,
        updated_at=pref.updated_at,
    )


@router.put("/preferences", response_model=PreferenceOut)
async def update_preferences(
    payload: PreferenceUpdate,
    session: SessionDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> PreferenceOut:
    updates: dict = {}
    if payload.in_app_enabled is not None:
        updates["in_app_enabled"] = payload.in_app_enabled
    if payload.email_enabled is not None:
        updates["email_enabled"] = payload.email_enabled
    if payload.email_address is not None:
        updates["email_address"] = payload.email_address
    if payload.wechat_webhook_url is not None:
        updates["wechat_webhook_enc"] = _encrypt(
            payload.wechat_webhook_url, settings.encryption_key
        )
    if payload.dingtalk_webhook_url is not None:
        updates["dingtalk_webhook_enc"] = _encrypt(
            payload.dingtalk_webhook_url, settings.encryption_key
        )

    repo = NotificationRepository(session)
    pref = await repo.upsert_preference(tenant_id=tenant_id, user_id=user_id, **updates)

    return PreferenceOut(
        id=pref.id,
        in_app_enabled=pref.in_app_enabled,
        email_enabled=pref.email_enabled,
        email_address=pref.email_address,
        wechat_configured=pref.wechat_webhook_enc is not None,
        dingtalk_configured=pref.dingtalk_webhook_enc is not None,
        created_at=pref.created_at,
        updated_at=pref.updated_at,
    )
