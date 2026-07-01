#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Deploy JobCopilot to a remote server (run from your LOCAL machine).
# Provider-agnostic: any Ubuntu VPS reachable over SSH (tested on Hetzner Cloud).
#
#   SERVER_IP=178.105.84.44 ./infra/scripts/deploy.sh
#
# Strategy (chosen path: CI builds -> GHCR -> server pulls):
#   • Images are NOT built on the server. The CD workflow already builds, scans,
#     and pushes ghcr.io/<owner>/jobcopilot-<svc>:<sha> on every green main commit.
#   • This script pins IMAGE_TAG to the current git commit, ships only the infra/
#     config + the cloud env file, then `docker compose pull && up -d --no-build`.
#
# Requires:
#   • A clean git tree on a commit whose images CD has built (i.e. pushed to main)
#   • infra/.env.production filled in (template: .env.example "Cloud Deployment")
#   • GHCR packages public (no registry login needed on the server)
#
# Env vars:
#   SERVER_IP   (required) public IP of the server
#   SSH_USER    (default: root)
#   SSH_KEY     (optional) private key path; unset = your default SSH config
#   REMOTE_DIR  (default: /opt/jobcopilot)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SERVER_IP="${SERVER_IP:?set SERVER_IP=<your.server.ip>}"
SSH_USER="${SSH_USER:-root}"
SSH_KEY="${SSH_KEY:-}"
REMOTE_DIR="${REMOTE_DIR:-/opt/jobcopilot}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/infra/.env.production"
COMPOSE=(-f docker-compose.yml -f docker-compose.prod.yml)

SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
[ -n "$SSH_KEY" ] && SSH_OPTS+=(-i "$SSH_KEY")
TARGET="${SSH_USER}@${SERVER_IP}"
ssh_() { ssh "${SSH_OPTS[@]}" "$TARGET" "$@"; }

# 1. Reproducibility: refuse a dirty tree, pin to the current commit.
if [ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]; then
  echo "ERROR: working tree is dirty. Commit/push first so the deployed commit is" >&2
  echo "       reproducible and its images exist in GHCR." >&2
  exit 1
fi
TAG="$(git -C "$REPO_ROOT" rev-parse HEAD)"
if ! git -C "$REPO_ROOT" merge-base --is-ancestor "$TAG" origin/main 2>/dev/null; then
  echo "WARNING: HEAD is not on origin/main — CD only builds main, so GHCR may not" >&2
  echo "         have images for $TAG. Continuing in 5s (Ctrl-C to abort) ..." >&2
  sleep 5
fi

# 2. Cloud env must exist and be real.
[ -f "$ENV_FILE" ] || {
  echo "ERROR: $ENV_FILE missing. Copy the 'Cloud Deployment' block from" >&2
  echo "       infra/.env.example into infra/.env.production and fill it in." >&2
  exit 1
}
for v in SERVER_HOST KEYCLOAK_PUBLIC_URL FRONTEND_PUBLIC_URL ENCRYPTION_KEY \
         POSTGRES_PASSWORD RABBITMQ_PASSWORD KEYCLOAK_ADMIN_PASSWORD; do
  grep -qE "^${v}=.+" "$ENV_FILE" || { echo "ERROR: $v is empty in .env.production" >&2; exit 1; }
done
grep -qE "^ENCRYPTION_KEY=0{64}$" "$ENV_FILE" && {
  echo "ERROR: ENCRYPTION_KEY is still the all-zero dev placeholder." >&2; exit 1; }

# 3. Provision the server (idempotent).
echo "==> Provisioning ${TARGET} ..."
ssh_ "mkdir -p ${REMOTE_DIR}"
rsync -az -e "ssh ${SSH_OPTS[*]}" \
  "$REPO_ROOT/infra/scripts/server-setup.sh" "${TARGET}:${REMOTE_DIR}/server-setup.sh"
ssh_ "bash ${REMOTE_DIR}/server-setup.sh"

# 4. Ship infra/ config (NOT source; images come from GHCR) + the cloud env file.
echo "==> Syncing infra/ config + env (IMAGE_TAG=${TAG:0:12}) ..."
rsync -az --delete -e "ssh ${SSH_OPTS[*]}" \
  --exclude '.env' --exclude '.env.*' \
  "$REPO_ROOT/infra/" "${TARGET}:${REMOTE_DIR}/infra/"
rsync -az -e "ssh ${SSH_OPTS[*]}" "$ENV_FILE" "${TARGET}:${REMOTE_DIR}/infra/.env"
ssh_ "cd ${REMOTE_DIR}/infra \
      && (grep -q '^IMAGE_TAG=' .env && sed -i 's|^IMAGE_TAG=.*|IMAGE_TAG=${TAG}|' .env || echo 'IMAGE_TAG=${TAG}' >> .env) \
      && chmod 600 .env"

# 5. Pull pinned images and (re)start. --no-build guarantees nothing builds on prod.
echo "==> Pulling images + starting stack ..."
ssh_ "cd ${REMOTE_DIR}/infra && docker compose ${COMPOSE[*]} pull && docker compose ${COMPOSE[*]} up -d --no-build --remove-orphans"

SERVER_HOST="$(grep -E '^SERVER_HOST=' "$ENV_FILE" | cut -d= -f2-)"
echo ""
echo "==> Deploy complete (commit ${TAG:0:12})."
echo "    Frontend : https://${SERVER_HOST}"
echo "    Keycloak : https://auth.${SERVER_HOST}"
echo "    Logs     : ssh ${TARGET} 'cd ${REMOTE_DIR}/infra && docker compose ${COMPOSE[*]} logs -f'"
