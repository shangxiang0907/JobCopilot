import asyncio
import os
import time
import uuid
from typing import Annotated, Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.exceptions import JWKError
from pydantic import BaseModel

_security = HTTPBearer()

_jwks_cache: dict[str, Any] | None = None
_jwks_fetched_at: float = 0.0
_jwks_lock: asyncio.Lock | None = None
_JWKS_TTL = 3600.0


def _get_lock() -> asyncio.Lock:
    global _jwks_lock
    if _jwks_lock is None:
        _jwks_lock = asyncio.Lock()
    return _jwks_lock


def _jwks_uri() -> str:
    url = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
    realm = os.getenv("KEYCLOAK_REALM", "jobcopilot")
    return f"{url}/realms/{realm}/protocol/openid-connect/certs"


def _expected_issuer() -> str:
    # KEYCLOAK_ISSUER_URL is the public-facing URL embedded in JWT iss claims.
    # It may differ from KEYCLOAK_URL (internal Docker/K8s hostname used for JWKS fetch).
    url = os.getenv("KEYCLOAK_ISSUER_URL") or os.getenv("KEYCLOAK_URL", "http://localhost:8080")
    realm = os.getenv("KEYCLOAK_REALM", "jobcopilot")
    return f"{url}/realms/{realm}"


async def _fetch_jwks(force: bool = False) -> dict[str, Any]:
    global _jwks_cache, _jwks_fetched_at
    now = time.monotonic()
    if not force and _jwks_cache is not None and (now - _jwks_fetched_at) < _JWKS_TTL:
        return _jwks_cache
    async with _get_lock():
        elapsed = time.monotonic() - _jwks_fetched_at
        if not force and _jwks_cache is not None and elapsed < _JWKS_TTL:
            return _jwks_cache
        async with httpx.AsyncClient() as client:
            resp = await client.get(_jwks_uri(), timeout=5.0)
            resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_fetched_at = time.monotonic()
    return _jwks_cache


class TokenClaims(BaseModel):
    sub: uuid.UUID
    tenant_id: uuid.UUID
    iss: str
    exp: int
    roles: list[str] = []


async def verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_security)],
) -> TokenClaims:
    token = credentials.credentials

    # Retry once with a fresh JWKS fetch to handle transparent key rotation.
    for attempt in range(2):
        try:
            jwks = await _fetch_jwks(force=attempt > 0)
            audience = os.getenv("KEYCLOAK_CLIENT_ID", "api")
            raw = jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                audience=audience,
            )
            break
        except JWKError as exc:
            if attempt > 0:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No valid signing key found",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from exc
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to fetch signing keys",
            ) from exc

    if raw.get("iss") != _expected_issuer():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        sub = uuid.UUID(str(raw["sub"]))
        # Self-registered users carry no tenant_id attribute: each user is
        # their own tenant (PRD v0.2 §2), so identity defaults to sub. An
        # explicit claim (legacy/managed users) always wins.
        tenant_id = uuid.UUID(str(raw["tenant_id"])) if raw.get("tenant_id") else sub
        return TokenClaims(
            sub=sub,
            tenant_id=tenant_id,
            iss=raw["iss"],
            exp=int(raw["exp"]),
            roles=list((raw.get("realm_access") or {}).get("roles") or []),
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claims",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


TokenClaimsDep = Annotated[TokenClaims, Depends(verify_token)]


async def require_admin(claims: TokenClaimsDep) -> TokenClaims:
    """Guard for /v1/admin/* endpoints — platform operator only (realm role `admin`)."""
    if "admin" not in claims.roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return claims


AdminClaimsDep = Annotated[TokenClaims, Depends(require_admin)]
