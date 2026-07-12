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
