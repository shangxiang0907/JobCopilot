#!/usr/bin/env python3
"""
Periodic cleanup of never-verified Keycloak users past a TTL.

Why: with registrationEmailAsUsername, an unverified registration squats the
email — the real owner cannot self-register until the record is gone (they CAN
claim it immediately via "Forgot password", but should not have to know that).
Unverified records also hold PII of people who never completed sign-up (GDPR
data minimisation). Keycloak has no built-in expiry for them.

Safety: deletes ONLY users with emailVerified=false whose createdTimestamp is
older than UNVERIFIED_USER_TTL_HOURS. Unverified users have never passed the
login gate, so they own no application data — deleting the Keycloak record is
the complete cleanup (activated-account deletion is a separate, cross-service
concern). Auth uses the least-privilege `admin-api` service account
(view-users + manage-users), never the master admin credentials.

Set CLEANUP_INTERVAL_SECONDS<=0 to run a single pass and exit (used in tests).
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
CLIENT_ID = "admin-api"
CLIENT_SECRET = os.environ.get("KEYCLOAK_ADMIN_API_SECRET", "")
TTL_HOURS = float(os.environ.get("UNVERIFIED_USER_TTL_HOURS", "24"))
INTERVAL_SECONDS = int(os.environ.get("CLEANUP_INTERVAL_SECONDS", "3600"))
PAGE_SIZE = 100


def _http(
    method: str, url: str, data: bytes | None = None, token: str | None = None
) -> dict | list:
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


def get_service_token() -> str:
    url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
    payload = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }
    ).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["access_token"]


def cleanup_pass() -> None:
    token = get_service_token()
    cutoff_ms = (time.time() - TTL_HOURS * 3600) * 1000
    users_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/users"

    stale: list[dict] = []
    first = 0
    while True:
        page = _http(
            "GET", f"{users_url}?emailVerified=false&first={first}&max={PAGE_SIZE}", token=token
        )
        if not isinstance(page, list):
            raise TypeError(f"expected a user list from {users_url}, got {type(page).__name__}")
        for user in page:
            # Server-side filter is re-checked here: never trust a query param
            # alone when the failure mode is deleting the wrong account.
            if user.get("emailVerified"):
                continue
            # Client service accounts (username `service-account-<client>`) are
            # emailVerified=false too — deleting them bricks their client,
            # including the very account this script authenticates as.
            if str(user.get("username", "")).startswith("service-account-"):
                continue
            # Registration always captures an email (email-as-username); a
            # record without one is not a self-registration — leave it alone.
            if not user.get("email"):
                continue
            created = user.get("createdTimestamp")
            if created is None or created >= cutoff_ms:
                continue
            stale.append(user)
        if len(page) < PAGE_SIZE:
            break
        first += PAGE_SIZE

    if not stale:
        print(f"==> no unverified users older than {TTL_HOURS:g}h — nothing to do", flush=True)
        return

    for user in stale:
        _http("DELETE", f"{users_url}/{user['id']}", token=token)
        age_h = (time.time() * 1000 - user["createdTimestamp"]) / 3_600_000
        print(
            f"==> deleted unverified user '{user.get('username')}' (age {age_h:.1f}h)", flush=True
        )


def main() -> None:
    if not CLIENT_SECRET:
        print("==> KEYCLOAK_ADMIN_API_SECRET unset — cleanup disabled", flush=True)
        return
    while True:
        try:
            cleanup_pass()
        except Exception as exc:  # noqa: BLE001 — a failed pass must not kill the loop
            print(f"==> cleanup pass failed: {exc}", file=sys.stderr, flush=True)
        if INTERVAL_SECONDS <= 0:
            return
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
