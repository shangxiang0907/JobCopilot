"""Minimal Keycloak Admin API client for platform-admin user management.

Authenticates as the `admin-api` service account (client_credentials, scoped
to view-users + manage-users by keycloak-init) — the master admin password
never reaches application services.
"""

import time
from typing import Any

import httpx

from jobcopilot_profile.config import settings

_token_cache: dict[str, Any] = {"token": "", "expires_at": 0.0}


async def _admin_token(client: httpx.AsyncClient) -> str:
    if _token_cache["token"] and time.monotonic() < _token_cache["expires_at"]:
        return str(_token_cache["token"])
    resp = await client.post(
        f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "admin-api",
            "client_secret": settings.keycloak_admin_api_secret,
        },
    )
    resp.raise_for_status()
    payload = resp.json()
    _token_cache["token"] = payload["access_token"]
    # Refresh 30s before expiry.
    _token_cache["expires_at"] = time.monotonic() + int(payload.get("expires_in", 60)) - 30
    return str(_token_cache["token"])


def _admin_base() -> str:
    return f"{settings.keycloak_url}/admin/realms/{settings.keycloak_realm}"


async def list_users(
    query: str = "", first: int = 0, max_results: int = 20
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        token = await _admin_token(client)
        resp = await client.get(
            f"{_admin_base()}/users",
            params={"search": query, "first": first, "max": max_results},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        users: list[dict[str, Any]] = resp.json()
        return users


async def count_users() -> int:
    async with httpx.AsyncClient(timeout=10.0) as client:
        token = await _admin_token(client)
        resp = await client.get(
            f"{_admin_base()}/users/count",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return int(resp.json())


async def set_user_enabled(user_id: str, enabled: bool) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        token = await _admin_token(client)
        resp = await client.put(
            f"{_admin_base()}/users/{user_id}",
            json={"enabled": enabled},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
