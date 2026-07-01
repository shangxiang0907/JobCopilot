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
import urllib.error
import urllib.parse
import urllib.request

KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://keycloak:8080")
REALM = os.environ.get("KEYCLOAK_REALM", "jobcopilot")
ADMIN_USER = os.environ.get("KEYCLOAK_ADMIN", "admin")
ADMIN_PASS = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "admin")
ATTRIBUTE_NAME = "tenant_id"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
FRONTEND_CLIENT_ID = "frontend"


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


def get_admin_token() -> str:
    url = f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token"
    payload = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": ADMIN_USER,
            "password": ADMIN_PASS,
        }
    ).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["access_token"]


def configure_user_profile(token: str) -> None:
    """Declare the `tenant_id` attribute in the Declarative User Profile."""
    profile_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/users/profile"

    print("==> Fetching current User Profile configuration ...")
    profile = _http("GET", profile_url, token=token)

    attributes = profile.get("attributes", [])
    if any(a.get("name") == ATTRIBUTE_NAME for a in attributes):
        print(f"==> '{ATTRIBUTE_NAME}' already declared in User Profile — nothing to do")
        return

    attributes.append(
        {
            "name": ATTRIBUTE_NAME,
            "displayName": "Tenant ID",
            "permissions": {
                "view": ["admin"],
                "edit": ["admin"],
            },
            "validations": {},
            "annotations": {},
        }
    )
    profile["attributes"] = attributes

    print(f"==> Adding '{ATTRIBUTE_NAME}' to User Profile ...")
    _http("PUT", profile_url, data=json.dumps(profile).encode(), token=token)
    print(f"==> '{ATTRIBUTE_NAME}' User Profile attribute configured successfully")


def ensure_redirect_uri(token: str) -> None:
    """Ensure the frontend client trusts FRONTEND_URL as a redirect URI + web origin.

    Cloud deployments serve the SPA from a public domain that differs from the
    localhost defaults baked into the realm export. Without this, Keycloak rejects
    the OIDC redirect back to the app and blocks the browser token request (CORS).
    Idempotent: only PUTs when something is missing.
    """
    clients_url = (
        f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients"
        f"?clientId={urllib.parse.quote(FRONTEND_CLIENT_ID)}"
    )
    clients = _http("GET", clients_url, token=token)
    if not clients:
        print(f"==> client '{FRONTEND_CLIENT_ID}' not found — skipping redirect URI")
        return

    client = clients[0]
    redirect = f"{FRONTEND_URL}/*"
    redirect_uris = client.get("redirectUris", [])
    web_origins = client.get("webOrigins", [])
    changed = False

    if redirect not in redirect_uris:
        redirect_uris.append(redirect)
        changed = True
    if FRONTEND_URL not in web_origins:
        web_origins.append(FRONTEND_URL)
        changed = True

    if not changed:
        print(f"==> redirect URI '{redirect}' already present — nothing to do")
        return

    client["redirectUris"] = redirect_uris
    client["webOrigins"] = web_origins
    client_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients/{client['id']}"
    print(f"==> Adding redirect URI '{redirect}' + web origin to '{FRONTEND_CLIENT_ID}' ...")
    _http("PUT", client_url, data=json.dumps(client).encode(), token=token)
    print("==> frontend client redirect URI / web origin configured successfully")


def main() -> None:
    print("==> Fetching admin token ...")
    token = get_admin_token()
    configure_user_profile(token)
    ensure_redirect_uri(token)


if __name__ == "__main__":
    main()
