"""Platform-admin user management (PRD v0.2 §3.10) — realm role `admin` only."""

import logging

from fastapi import APIRouter, Query
from jobcopilot_shared.auth import AdminClaimsDep
from jobcopilot_shared.schemas.common import PaginatedResponse
from pydantic import BaseModel

from jobcopilot_profile.services import keycloak_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/admin/users", tags=["admin"])

_PAGE_SIZE = 20


class AdminUser(BaseModel):
    id: str
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    enabled: bool = True
    email_verified: bool = False
    created_at_ms: int = 0


class UserEnabledUpdate(BaseModel):
    enabled: bool


@router.get("", response_model=PaginatedResponse[AdminUser])
async def admin_list_users(
    claims: AdminClaimsDep,
    q: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
) -> PaginatedResponse[AdminUser]:
    users = await keycloak_admin.list_users(
        query=q, first=(page - 1) * _PAGE_SIZE, max_results=_PAGE_SIZE
    )
    total = await keycloak_admin.count_users()
    items = [
        AdminUser(
            id=u["id"],
            email=u.get("email", ""),
            first_name=u.get("firstName", ""),
            last_name=u.get("lastName", ""),
            enabled=bool(u.get("enabled", True)),
            email_verified=bool(u.get("emailVerified", False)),
            created_at_ms=int(u.get("createdTimestamp", 0)),
        )
        for u in users
    ]
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=_PAGE_SIZE,
        has_next=page * _PAGE_SIZE < total,
    )


@router.patch("/{user_id}", status_code=204)
async def admin_set_user_enabled(
    user_id: str,
    body: UserEnabledUpdate,
    claims: AdminClaimsDep,
) -> None:
    await keycloak_admin.set_user_enabled(user_id, body.enabled)
    logger.info(
        "admin_user_enabled_changed",
        extra={"target_user": user_id, "enabled": body.enabled, "by": str(claims.sub)},
    )
