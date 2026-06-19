#!/usr/bin/env python3
"""
Idempotent init script: declares the `tenant_id` attribute in Keycloak's
Declarative User Profile so the oidc-usermodel-attribute-mapper can read it
and include it in JWT access tokens.

Run after Keycloak is healthy (Docker Compose: depends_on service_healthy;
Kubernetes: initContainer or Job after readiness probe passes).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://keycloak:8080")
REALM = os.environ.get("KEYCLOAK_REALM", "jobcopilot")
ADMIN_USER = os.environ.get("KEYCLOAK_ADMIN", "admin")
ADMIN_PASS = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "admin")
ATTRIBUTE_NAME = "tenant_id"


def _http(method: str, url: str, data: bytes | None = None, token: str | None = None) -> dict:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        print(f"HTTP {exc.code} {method} {url}: {body}", file=sys.stderr)
        raise


def wait_for_keycloak(max_wait: int = 120) -> None:
    health_url = f"{KEYCLOAK_URL}/health/ready"
    deadline = time.monotonic() + max_wait
    print(f"==> Waiting for Keycloak at {health_url} ...")
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=5) as resp:
                if resp.status == 200:
                    print("==> Keycloak is ready")
                    return
        except Exception:
            pass
        time.sleep(3)
    print("ERROR: Keycloak did not become ready in time", file=sys.stderr)
    sys.exit(1)


def get_admin_token() -> str:
    url = f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token"
    payload = urllib.parse.urlencode({
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": ADMIN_USER,
        "password": ADMIN_PASS,
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["access_token"]


def main() -> None:
    wait_for_keycloak()

    print("==> Fetching admin token ...")
    token = get_admin_token()

    profile_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/users/profile"

    print("==> Fetching current User Profile configuration ...")
    profile = _http("GET", profile_url, token=token)

    attributes = profile.get("attributes", [])
    if any(a.get("name") == ATTRIBUTE_NAME for a in attributes):
        print(f"==> '{ATTRIBUTE_NAME}' already declared in User Profile — nothing to do")
        return

    attributes.append({
        "name": ATTRIBUTE_NAME,
        "displayName": "Tenant ID",
        "permissions": {
            "view": ["admin"],
            "edit": ["admin"],
        },
        "validations": {},
        "annotations": {},
    })
    profile["attributes"] = attributes

    print(f"==> Adding '{ATTRIBUTE_NAME}' to User Profile ...")
    _http("PUT", profile_url, data=json.dumps(profile).encode(), token=token)
    print(f"==> '{ATTRIBUTE_NAME}' User Profile attribute configured successfully")


if __name__ == "__main__":
    main()
