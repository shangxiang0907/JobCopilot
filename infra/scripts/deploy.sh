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
#   • The deploy ITSELF runs on the server, in infra/scripts/remote-deploy.sh,
#     reached through the same /usr/local/bin/jobcopilot-deploy gate that CD uses.
#     This script does only what a local machine can do that the server cannot:
#     prove the tree is clean, prove CD went green, and install the secrets.
#     One implementation means a hand-run deploy and an automated one cannot
#     drift apart — the failure mode where the manual path quietly still works
#     and the CI path has been broken for weeks.
#
# Rollback: redeploy any older commit whose images CD already built.
#   GIT_REF=<old-commit-sha> SERVER_IP=<ip> ./infra/scripts/deploy.sh
# Since 2026-08-04 this rolls back the infra/ CONFIG as well as the images: the
# server checks out the commit being deployed, so deploying commit X ships X's
# compose files and Caddyfile. (Previously the config came from your current
# tree while only the images moved — reproducible only by accident.)
#
# Requires:
#   • A clean git tree; GIT_REF must resolve to a commit whose images exist in GHCR
#     (i.e. a commit CD built after it was pushed to main)
#   • gh CLI authenticated (verifies the commit's CD run — incl. the blocking
#     Trivy image scan — concluded green before anything is deployed)
#   • infra/.env.production filled in (template: .env.example "Cloud Deployment")
#   • /usr/local/bin/jobcopilot-deploy installed on the server (see that script's
#     header; it is also what the CD deploy key is pinned to)
#   • GHCR packages public (no registry login needed on the server)
#
# Env vars:
#   SERVER_IP    (required) public IP of the server
#   GIT_REF      (default: HEAD) commit to deploy; set to an older SHA to roll back
#   SSH_USER     (default: root) — needs root: provisions the host and installs .env
#   SSH_KEY      (optional) private key path; unset = your default SSH config
#   REMOTE_DIR   (default: /opt/jobcopilot)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SERVER_IP="${SERVER_IP:?set SERVER_IP=<your.server.ip>}"
GIT_REF="${GIT_REF:-HEAD}"
SSH_USER="${SSH_USER:-root}"
SSH_KEY="${SSH_KEY:-}"
REMOTE_DIR="${REMOTE_DIR:-/opt/jobcopilot}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/infra/.env.production"

SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
[ -n "$SSH_KEY" ] && SSH_OPTS+=(-i "$SSH_KEY")
TARGET="${SSH_USER}@${SERVER_IP}"
ssh_() { ssh "${SSH_OPTS[@]}" "$TARGET" "$@"; }

# 1. Reproducibility: refuse a dirty tree, pin to the requested commit (GIT_REF).
if [ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]; then
  echo "ERROR: working tree is dirty. Commit/push first so the deployed commit is" >&2
  echo "       reproducible and its images exist in GHCR." >&2
  exit 1
fi
TAG="$(git -C "$REPO_ROOT" rev-parse "$GIT_REF")" || {
  echo "ERROR: GIT_REF='$GIT_REF' is not a valid git commit." >&2; exit 1; }
if ! git -C "$REPO_ROOT" merge-base --is-ancestor "$TAG" origin/main 2>/dev/null; then
  echo "ERROR: ${GIT_REF} (${TAG:0:12}) is not on origin/main. CD only builds main," >&2
  echo "       so GHCR has no images for it, and the server refuses non-main" >&2
  echo "       commits regardless. Push it to main first." >&2
  exit 1
fi

# 1b. Supply-chain gate: the commit's CD run (image build + blocking Trivy scan)
#     must have concluded green. Resolving a digest only proves an image EXISTS
#     in GHCR — CD pushes images BEFORE scanning them, so a commit whose
#     image-scan job failed still has pullable images. Never deploy those.
command -v gh >/dev/null 2>&1 || {
  echo "ERROR: gh CLI not found — required to verify the CD run (incl. Trivy" >&2
  echo "       image scan) passed for ${TAG:0:12}. Install: https://cli.github.com" >&2
  exit 1
}
cd_state="$(gh run list --workflow CD --commit "$TAG" --limit 1 \
              --json status,conclusion --jq '.[0] | "\(.status)/\(.conclusion)"' \
              2>/dev/null || true)"
case "$cd_state" in
  completed/success)
    echo "==> CD run for ${TAG:0:12} is green (build + image scan passed)." ;;
  ""|null/null)
    echo "ERROR: no CD run found for commit ${TAG:0:12}. Push it to main and wait" >&2
    echo "       for CD to finish:  gh run watch" >&2
    exit 1 ;;
  in_progress/*|queued/*|pending/*|waiting/*)
    echo "ERROR: CD run for ${TAG:0:12} has not finished (${cd_state%%/*})." >&2
    echo "       Wait for it:  gh run watch" >&2
    exit 1 ;;
  *)
    echo "ERROR: CD run for ${TAG:0:12} did not succeed (state: ${cd_state})." >&2
    echo "       Its Trivy image scan may have found Critical CVEs. Inspect with:" >&2
    echo "       gh run list --workflow CD --commit ${TAG}" >&2
    exit 1 ;;
esac

# 2. Cloud env must exist and be real.
[ -f "$ENV_FILE" ] || {
  echo "ERROR: $ENV_FILE missing. Copy the 'Cloud Deployment' block from" >&2
  echo "       infra/.env.example into infra/.env.production and fill it in." >&2
  exit 1
}
for v in SERVER_HOST KEYCLOAK_PUBLIC_URL FRONTEND_PUBLIC_URL ENCRYPTION_KEY \
         POSTGRES_PASSWORD RABBITMQ_PASSWORD KEYCLOAK_ADMIN_PASSWORD \
         GRAFANA_ADMIN_PASSWORD; do
  grep -qE "^${v}=.+" "$ENV_FILE" || { echo "ERROR: $v is empty in .env.production" >&2; exit 1; }
done
grep -qE "^ENCRYPTION_KEY=0{64}$" "$ENV_FILE" && {
  echo "ERROR: ENCRYPTION_KEY is still the all-zero dev placeholder." >&2; exit 1; }
grep -qE '^COMPOSE_PROFILES=.*offsite-backup' "$ENV_FILE" || {
  echo "WARNING: offsite backup sync is NOT enabled — DB backups exist only on the" >&2
  echo "         server's own disk. Set COMPOSE_PROFILES=offsite-backup plus the" >&2
  echo "         BACKUP_S3_* vars in .env.production (see .env.example)." >&2; }

# 3. Provision the server (idempotent). Needs root, which is exactly why CD does
#    NOT do this: the account CD logs in as never needs to install anything.
echo "==> Provisioning ${TARGET} ..."
ssh_ "mkdir -p ${REMOTE_DIR}"
rsync -az -e "ssh ${SSH_OPTS[*]}" \
  "$REPO_ROOT/infra/scripts/server-setup.sh" "${TARGET}:${REMOTE_DIR}/server-setup.sh"
ssh_ "bash ${REMOTE_DIR}/server-setup.sh"

# 4. Install the production secrets. This is the ONLY channel by which .env
#    reaches the server, and it is deliberately human-run: CD has no copy of
#    these values and no way to ask for one, so a compromised CD key cannot
#    exfiltrate them. Digest pins are appended server-side, so strip nothing here.
echo "==> Installing infra/.env (production secrets) ..."
rsync -az -e "ssh ${SSH_OPTS[*]}" "$ENV_FILE" "${TARGET}:${REMOTE_DIR}/infra/.env"
ssh_ "chmod 600 ${REMOTE_DIR}/infra/.env"

# 5. Hand off to the server. Same entry point CD uses, same validation, same
#    deploy implementation — see infra/scripts/remote-deploy.sh.
ssh_ "/usr/local/bin/jobcopilot-deploy deploy ${TAG}" || {
  echo "" >&2
  echo "ERROR: the deploy failed on the server. If the shim is missing, install" >&2
  echo "       it once (from this checkout):" >&2
  echo "         scp infra/scripts/jobcopilot-deploy ${TARGET}:/usr/local/bin/" >&2
  echo "         ssh ${TARGET} 'chmod 755 /usr/local/bin/jobcopilot-deploy'" >&2
  exit 1
}

echo "    Logs     : ssh ${TARGET} 'cd ${REMOTE_DIR}/infra && docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f'"
