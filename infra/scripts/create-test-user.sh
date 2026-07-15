#!/usr/bin/env bash
# Idempotently create the E2E test user in the jobcopilot realm.
# Used by the CD e2e-smoke job (fresh Keycloak volume on every run) and safe
# to run against a local dev stack where the user already exists.
set -euo pipefail

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8080}"
ADMIN_USER="${KEYCLOAK_ADMIN:-admin}"
ADMIN_PASS="${KEYCLOAK_ADMIN_PASSWORD:-admin}"
REALM="${KEYCLOAK_REALM:-jobcopilot}"
E2E_USER="${E2E_USER:-testuser@example.com}"
E2E_PASSWORD="${E2E_PASSWORD:-Test1234!}"
TENANT_ID="${E2E_TENANT_ID:-$(cat /proc/sys/kernel/random/uuid)}"

token=$(curl -sf "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  -d grant_type=password -d client_id=admin-cli \
  -d "username=$ADMIN_USER" -d "password=$ADMIN_PASS" |
  sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

if [ -z "$token" ]; then
  echo "ERROR: could not obtain Keycloak admin token" >&2
  exit 1
fi

status=$(curl -s -o /dev/null -w '%{http_code}' \
  -X POST "$KEYCLOAK_URL/admin/realms/$REALM/users" \
  -H "Authorization: Bearer $token" -H "Content-Type: application/json" \
  -d "{
    \"username\": \"$E2E_USER\",
    \"email\": \"$E2E_USER\",
    \"emailVerified\": true,
    \"enabled\": true,
    \"firstName\": \"E2E\",
    \"lastName\": \"Test\",
    \"attributes\": {\"tenant_id\": [\"$TENANT_ID\"]},
    \"credentials\": [{\"type\": \"password\", \"value\": \"$E2E_PASSWORD\", \"temporary\": false}]
  }")

case "$status" in
  201) echo "Test user $E2E_USER created (tenant_id=$TENANT_ID)" ;;
  409) echo "Test user $E2E_USER already exists — nothing to do" ;;
  *)
    echo "ERROR: user creation returned HTTP $status" >&2
    exit 1
    ;;
esac

# Grant the realm role `admin` so the E2E smoke can exercise the /admin pages.
# Re-adding an existing mapping is a no-op in Keycloak, so this is idempotent.
# Lookup by email, not username: Keycloak returns [] for a `username=` search
# containing "@" even when the username is exactly that (verified empirically).
email_encoded=$(printf '%s' "$E2E_USER" | sed 's/@/%40/')
user_id=$(curl -sf "$KEYCLOAK_URL/admin/realms/$REALM/users?email=$email_encoded&exact=true" \
  -H "Authorization: Bearer $token" |
  sed -n 's/.*"id":"\([^"]*\)".*/\1/p')

if [ -z "$user_id" ]; then
  echo "ERROR: could not resolve user id for $E2E_USER" >&2
  exit 1
fi

admin_role=$(curl -sf "$KEYCLOAK_URL/admin/realms/$REALM/roles/admin" \
  -H "Authorization: Bearer $token")

status=$(curl -s -o /dev/null -w '%{http_code}' \
  -X POST "$KEYCLOAK_URL/admin/realms/$REALM/users/$user_id/role-mappings/realm" \
  -H "Authorization: Bearer $token" -H "Content-Type: application/json" \
  -d "[$admin_role]")

if [ "$status" != "204" ]; then
  echo "ERROR: admin role grant returned HTTP $status" >&2
  exit 1
fi
echo "Realm role 'admin' granted to $E2E_USER"
