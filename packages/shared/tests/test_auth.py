"""Unit tests for JWT validation (jobcopilot_shared.auth.verify_token).

Tokens are signed with a locally generated RSA key; the JWKS fetch is
monkeypatched so no Keycloak instance is needed.
"""

import time
import uuid
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jobcopilot_shared import auth
from jose import jwk, jwt

_KID = "test-key"
_ISSUER = "http://keycloak.test/realms/jobcopilot"
_AUDIENCE = "api"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIVATE_PEM = _private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
_PUBLIC_PEM = (
    _private_key.public_key()
    .public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)

_other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_PRIVATE_PEM = _other_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()


def _jwks() -> dict[str, Any]:
    public_jwk = jwk.construct(_PUBLIC_PEM, "RS256").to_dict()
    public_jwk["kid"] = _KID
    return {"keys": [public_jwk]}


def _make_token(
    *,
    sub: str | None = None,
    tenant_id: str | None = None,
    iss: str = _ISSUER,
    aud: str = _AUDIENCE,
    exp_offset: int = 300,
    signing_key: str = _PRIVATE_PEM,
) -> str:
    claims: dict[str, Any] = {
        "iss": iss,
        "aud": aud,
        "exp": int(time.time()) + exp_offset,
        "sub": sub if sub is not None else str(uuid.uuid4()),
    }
    if tenant_id != "":
        claims["tenant_id"] = tenant_id if tenant_id is not None else str(uuid.uuid4())
    token: str = jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": _KID})
    return token


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak.test")
    monkeypatch.setenv("KEYCLOAK_REALM", "jobcopilot")
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", _AUDIENCE)
    monkeypatch.delenv("KEYCLOAK_ISSUER_URL", raising=False)

    async def fake_fetch_jwks(force: bool = False) -> dict[str, Any]:
        return _jwks()

    monkeypatch.setattr(auth, "_fetch_jwks", fake_fetch_jwks)


async def test_valid_token_returns_claims() -> None:
    sub = str(uuid.uuid4())
    tenant = str(uuid.uuid4())
    claims = await auth.verify_token(_credentials(_make_token(sub=sub, tenant_id=tenant)))
    assert claims.sub == uuid.UUID(sub)
    assert claims.tenant_id == uuid.UUID(tenant)
    assert claims.iss == _ISSUER


async def test_expired_token_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        await auth.verify_token(_credentials(_make_token(exp_offset=-60)))
    assert exc.value.status_code == 401


async def test_wrong_audience_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        await auth.verify_token(_credentials(_make_token(aud="not-the-api")))
    assert exc.value.status_code == 401


async def test_wrong_issuer_rejected() -> None:
    token = _make_token(iss="http://evil.example/realms/jobcopilot")
    with pytest.raises(HTTPException) as exc:
        await auth.verify_token(_credentials(token))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token issuer"


async def test_missing_tenant_id_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        await auth.verify_token(_credentials(_make_token(tenant_id="")))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Token missing required claims"


async def test_non_uuid_tenant_id_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        await auth.verify_token(_credentials(_make_token(tenant_id="tenant-1")))
    assert exc.value.status_code == 401


async def test_garbage_token_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        await auth.verify_token(_credentials("not.a.jwt"))
    assert exc.value.status_code == 401


async def test_token_signed_with_unknown_key_rejected() -> None:
    token = _make_token(signing_key=_OTHER_PRIVATE_PEM)
    with pytest.raises(HTTPException) as exc:
        await auth.verify_token(_credentials(token))
    assert exc.value.status_code == 401
