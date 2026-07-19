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
    """Ensure the frontend client trusts FRONTEND_URL as a redirect URI + web origin,
    and as a post-logout redirect URI (RP-initiated logout).

    Cloud deployments serve the SPA from a public domain that differs from the
    localhost defaults baked into the realm export. Without this, Keycloak rejects
    the OIDC redirect back to the app and blocks the browser token request (CORS).
    Keycloak validates `post_logout_redirect_uri` against the separate
    `post.logout.redirect.uris` client attribute (##-separated), so the Sign out
    button breaks on any non-localhost domain unless it is maintained here too.
    `baseUrl` drives the "Back to Application" link on Keycloak info pages —
    without it, a verify-email link opened outside the registering browser
    session dead-ends on a static confirmation page (Keycloak 26.7 sets the
    password only AFTER email verification, so users must find their way back).
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
    attributes = client.get("attributes", {})
    post_logout = [u for u in attributes.get("post.logout.redirect.uris", "").split("##") if u]
    changed = False

    if redirect not in redirect_uris:
        redirect_uris.append(redirect)
        changed = True
    if FRONTEND_URL not in web_origins:
        web_origins.append(FRONTEND_URL)
        changed = True
    if redirect not in post_logout:
        post_logout.append(redirect)
        changed = True
    if client.get("baseUrl") != FRONTEND_URL:
        client["baseUrl"] = FRONTEND_URL
        changed = True

    if not changed:
        print(f"==> redirect URI '{redirect}' already present — nothing to do")
        return

    client["redirectUris"] = redirect_uris
    client["webOrigins"] = web_origins
    attributes["post.logout.redirect.uris"] = "##".join(post_logout)
    client["attributes"] = attributes
    client_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients/{client['id']}"
    print(f"==> Adding redirect URI '{redirect}' + web origin to '{FRONTEND_CLIENT_ID}' ...")
    _http("PUT", client_url, data=json.dumps(client).encode(), token=token)
    print("==> frontend client redirect URI / web origin configured successfully")


def ensure_password_policy(token: str) -> None:
    """Enforce a minimal NIST-aligned password policy on the realm.

    length(8) + notUsername (username == email under registrationEmailAsUsername).
    Deliberately no complexity classes or expiry — NIST SP 800-63B recommends
    length over composition rules and no forced rotation. Appends missing
    policies rather than overwriting, so a stricter operator policy survives.
    """
    realm_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}"
    realm = _http("GET", realm_url, token=token)

    current = realm.get("passwordPolicy") or ""
    policies = [p.strip() for p in current.split(" and ") if p.strip()]
    existing_names = {p.split("(")[0] for p in policies}

    missing = [
        p for p in ("length(8)", "notUsername(undefined)") if p.split("(")[0] not in existing_names
    ]
    if not missing:
        print(f"==> password policy already enforced ('{current}') — nothing to do")
        return

    realm["passwordPolicy"] = " and ".join(policies + missing)
    print(f"==> Setting realm password policy '{realm['passwordPolicy']}' ...")
    _http("PUT", realm_url, data=json.dumps(realm).encode(), token=token)
    print("==> password policy configured successfully")


def ensure_self_registration(token: str) -> None:
    """Enable self-registration (PRD v0.2 B2C). Email verification switches on
    only when SMTP is configured — otherwise new users could never verify."""
    realm_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}"
    realm = _http("GET", realm_url, token=token)

    smtp_host = os.environ.get("SMTP_HOST", "")
    desired = {
        "registrationAllowed": True,
        "registrationEmailAsUsername": True,
        "verifyEmail": bool(smtp_host),
        "resetPasswordAllowed": True,
        "loginWithEmailAllowed": True,
    }
    if smtp_host:
        desired["smtpServer"] = {
            "host": smtp_host,
            "port": os.environ.get("SMTP_PORT", "587"),
            "from": os.environ.get("SMTP_FROM_ADDRESS", "noreply@jobcopilot.ai"),
            "fromDisplayName": "JobCopilot",
            "auth": "true" if os.environ.get("SMTP_USERNAME") else "false",
            "user": os.environ.get("SMTP_USERNAME", ""),
            "password": os.environ.get("SMTP_PASSWORD", ""),
            "starttls": os.environ.get("SMTP_USE_TLS", "true"),
            "ssl": "false",
        }

    # smtpServer comparison would leak the password into logs; compare flags only.
    flags_current = {k: realm.get(k) for k in desired if k != "smtpServer"}
    flags_desired = {k: v for k, v in desired.items() if k != "smtpServer"}
    if flags_current == flags_desired and not smtp_host:
        print("==> self-registration flags already set — nothing to do")
        return

    realm.update(desired)
    print(f"==> Enabling self-registration (verifyEmail={desired['verifyEmail']}) ...")
    _http("PUT", realm_url, data=json.dumps(realm).encode(), token=token)
    print("==> self-registration configured successfully")


def ensure_google_idp(token: str) -> None:
    """Register Google as an identity provider when credentials are supplied.

    Secrets arrive via env (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET) — never
    committed to the realm export. Skipped silently when unset.
    """
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        print("==> GOOGLE_CLIENT_ID/SECRET unset — skipping Google IdP")
        return

    idp_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/identity-provider/instances"
    payload = {
        "alias": "google",
        "providerId": "google",
        "enabled": True,
        "trustEmail": True,
        "config": {
            "clientId": client_id,
            "clientSecret": client_secret,
            "syncMode": "IMPORT",
        },
    }
    try:
        _http("GET", f"{idp_url}/google", token=token)
        print("==> Google IdP exists — updating credentials ...")
        _http("PUT", f"{idp_url}/google", data=json.dumps(payload).encode(), token=token)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        print("==> Creating Google IdP ...")
        _http("POST", idp_url, data=json.dumps(payload).encode(), token=token)
    print("==> Google IdP configured successfully")


def ensure_identity_provider_mapper(token: str) -> None:
    """Expose the broker alias (e.g. `google`) as an `identity_provider` claim.

    Keycloak records the broker used for a login in the `identity_provider`
    user-session note; a session-note protocol mapper surfaces it in tokens so
    the frontend can show "Signed in with Google". Password logins carry no
    such note, so the claim is simply absent for them.
    """
    clients_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients"
    clients = _http(
        "GET", f"{clients_url}?clientId={urllib.parse.quote(FRONTEND_CLIENT_ID)}", token=token
    )
    if not clients:
        print(f"==> client '{FRONTEND_CLIENT_ID}' not found — skipping identity_provider mapper")
        return

    client_uuid = clients[0]["id"]
    mappers_url = f"{clients_url}/{client_uuid}/protocol-mappers/models"
    existing = _http("GET", mappers_url, token=token)
    if any(m.get("name") == "identity-provider" for m in existing):
        print("==> identity_provider mapper already present — nothing to do")
        return

    payload = {
        "name": "identity-provider",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-usersessionmodel-note-mapper",
        "consentRequired": False,
        "config": {
            "user.session.note": "identity_provider",
            "claim.name": "identity_provider",
            "jsonType.label": "String",
            "id.token.claim": "true",
            "access.token.claim": "true",
        },
    }
    print("==> Adding identity_provider session-note mapper to frontend client ...")
    _http("POST", mappers_url, data=json.dumps(payload).encode(), token=token)
    print("==> identity_provider mapper configured successfully")


def ensure_admin_api_client(token: str) -> None:
    """Service-account client for the profile service's /v1/admin user management.

    Grants only realm-management view-users + manage-users (least privilege) —
    never the master admin credentials. Secret from KEYCLOAK_ADMIN_API_SECRET.
    """
    secret = os.environ.get("KEYCLOAK_ADMIN_API_SECRET", "")
    if not secret:
        print("==> KEYCLOAK_ADMIN_API_SECRET unset — skipping admin-api client")
        return

    clients_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients"
    existing = _http("GET", f"{clients_url}?clientId=admin-api", token=token)
    payload = {
        "clientId": "admin-api",
        "protocol": "openid-connect",
        "publicClient": False,
        "serviceAccountsEnabled": True,
        "standardFlowEnabled": False,
        "directAccessGrantsEnabled": False,
        "secret": secret,
    }
    if existing:
        client_uuid = existing[0]["id"]
        _http(
            "PUT",
            f"{clients_url}/{client_uuid}",
            data=json.dumps({**existing[0], **payload}).encode(),
            token=token,
        )
        print("==> admin-api client updated")
    else:
        _http("POST", clients_url, data=json.dumps(payload).encode(), token=token)
        client_uuid = _http("GET", f"{clients_url}?clientId=admin-api", token=token)[0]["id"]
        print("==> admin-api client created")

    # Assign realm-management roles to the service account.
    svc_user = _http("GET", f"{clients_url}/{client_uuid}/service-account-user", token=token)
    rm_client = _http("GET", f"{clients_url}?clientId=realm-management", token=token)[0]
    available = _http(
        "GET",
        f"{KEYCLOAK_URL}/admin/realms/{REALM}/users/{svc_user['id']}"
        f"/role-mappings/clients/{rm_client['id']}/available",
        token=token,
    )
    wanted = [r for r in available if r["name"] in ("view-users", "manage-users")]
    if wanted:
        _http(
            "POST",
            f"{KEYCLOAK_URL}/admin/realms/{REALM}/users/{svc_user['id']}"
            f"/role-mappings/clients/{rm_client['id']}",
            data=json.dumps(wanted).encode(),
            token=token,
        )
        print(f"==> granted {[r['name'] for r in wanted]} to admin-api service account")
    else:
        print("==> admin-api service account roles already granted")


def ensure_login_theme(token: str) -> None:
    """Point the realm at the custom 'jobcopilot' login theme (extends
    keycloak.v2; overrides login-verify-email.ftl so the verify-email waiting
    page is not a dead end when the link is opened on another device)."""
    realm_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}"
    realm = _http("GET", realm_url, token=token)

    if realm.get("loginTheme") == "jobcopilot":
        print("==> login theme already 'jobcopilot' — nothing to do")
        return

    realm["loginTheme"] = "jobcopilot"
    print("==> Setting realm login theme to 'jobcopilot' ...")
    _http("PUT", realm_url, data=json.dumps(realm).encode(), token=token)
    print("==> login theme configured successfully")


def ensure_action_token_lifespan(token: str) -> None:
    """Raise the user-initiated action token lifespan (email-verification /
    password-reset links) from Keycloak's 5-minute default to 30 minutes.
    Real users do not necessarily read their mailbox within 5 minutes; an
    expired link dead-ends on "Action expired" and forces a resend."""
    desired = 1800
    realm_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}"
    realm = _http("GET", realm_url, token=token)

    if realm.get("actionTokenGeneratedByUserLifespan") == desired:
        print(f"==> action token lifespan already {desired}s — nothing to do")
        return

    realm["actionTokenGeneratedByUserLifespan"] = desired
    print(f"==> Setting user action token lifespan to {desired}s ...")
    _http("PUT", realm_url, data=json.dumps(realm).encode(), token=token)
    print("==> action token lifespan configured successfully")


def main() -> None:
    print("==> Fetching admin token ...")
    token = get_admin_token()
    configure_user_profile(token)
    ensure_redirect_uri(token)
    ensure_password_policy(token)
    ensure_login_theme(token)
    ensure_action_token_lifespan(token)
    ensure_self_registration(token)
    ensure_google_idp(token)
    ensure_identity_provider_mapper(token)
    ensure_admin_api_client(token)


if __name__ == "__main__":
    main()
