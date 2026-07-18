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
#   • This script resolves each service's git-SHA tag to its IMMUTABLE DIGEST and
#     pins the prod overlay to `<image>@sha256:...` (a tag is mutable; a digest is
#     not). It ships only the infra/ config + the cloud env file, then
#     `docker compose pull && up -d --no-build`.
#
# Rollback: redeploy any older commit whose images CD already built. The infra/
# config shipped is your CURRENT (clean) tree; only the running images roll back:
#   GIT_REF=<old-commit-sha> SERVER_IP=<ip> ./infra/scripts/deploy.sh
# For a full rollback (config + images too), `git checkout <old>` first, then run.
#
# Requires:
#   • A clean git tree; GIT_REF must resolve to a commit whose images exist in GHCR
#     (i.e. a commit CD built after it was pushed to main)
#   • gh CLI authenticated (verifies the commit's CD run — incl. the blocking
#     Trivy image scan — concluded green before anything is deployed)
#   • infra/.env.production filled in (template: .env.example "Cloud Deployment")
#   • GHCR packages public (no registry login needed on the server)
#   • docker buildx (used locally to resolve tag -> digest; no image is pulled)
#
# Env vars:
#   SERVER_IP    (required) public IP of the server
#   GIT_REF      (default: HEAD) commit to deploy; set to an older SHA to roll back
#   GHCR_OWNER   (default: shangxiang0907) GHCR namespace owning the images
#   SSH_USER     (default: root)
#   SSH_KEY      (optional) private key path; unset = your default SSH config
#   REMOTE_DIR   (default: /opt/jobcopilot)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SERVER_IP="${SERVER_IP:?set SERVER_IP=<your.server.ip>}"
GIT_REF="${GIT_REF:-HEAD}"
GHCR_OWNER="${GHCR_OWNER:-shangxiang0907}"
SSH_USER="${SSH_USER:-root}"
SSH_KEY="${SSH_KEY:-}"
REMOTE_DIR="${REMOTE_DIR:-/opt/jobcopilot}"

# Service short name -> GHCR package suffix. The env var is <UPPER>_IMAGE_DIGEST
# (matches the ${..:?} refs in docker-compose.prod.yml).
SERVICES=(profile job discovery agent notification frontend)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/infra/.env.production"
COMPOSE=(-f docker-compose.yml -f docker-compose.prod.yml)

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
  echo "WARNING: ${GIT_REF} (${TAG:0:12}) is not on origin/main — CD only builds" >&2
  echo "         main, so GHCR may not have images for it. Continuing in 5s" >&2
  echo "         (Ctrl-C to abort) ..." >&2
  sleep 5
fi

# 1b. Supply-chain gate: the commit's CD run (image build + blocking Trivy scan)
#     must have concluded green. Resolving a digest (step 2b) only proves an image
#     EXISTS in GHCR — CD pushes images BEFORE scanning them, so a commit whose
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

# 2b. Resolve each service's git-SHA tag to its immutable digest (locally, no
#     pull). Fails hard if CD hasn't built this commit yet. Also builds the
#     PIN_ENV lines that pin the prod overlay to <image>@sha256:...
echo "==> Resolving image digests for ${TAG:0:12} (owner: ${GHCR_OWNER}) ..."
PIN_ENV="IMAGE_TAG=${TAG}"
declare -a DIGEST_ENVS=()
for svc in "${SERVICES[@]}"; do
  ref="ghcr.io/${GHCR_OWNER}/jobcopilot-${svc}:${TAG}"
  # `|| true`: under set -e -o pipefail a failed inspect would kill the script
  # inside the substitution, silently skipping the diagnostic below. Retry —
  # right after CD finishes, GHCR manifest propagation has been observed to
  # exceed 20s, so allow ~100s total before giving up.
  digest=""
  for attempt in 1 2 3 4 5 6; do
    digest="$(docker buildx imagetools inspect "$ref" 2>/dev/null | awk '/^Digest:/{print $2; exit}' || true)"
    [ -n "$digest" ] && break
    [ "$attempt" -lt 6 ] && { echo "    ${ref##*/}: not resolvable yet, retrying in 20s ..." >&2; sleep 20; }
  done
  if [ -z "$digest" ]; then
    echo "ERROR: could not resolve a digest for ${ref}." >&2
    echo "       Has CD finished building & pushing commit ${TAG:0:12} to GHCR?" >&2
    exit 1
  fi
  var="$(printf '%s' "$svc" | tr '[:lower:]' '[:upper:]')_IMAGE_DIGEST"
  echo "    jobcopilot-${svc} -> ${digest}"
  PIN_ENV="${PIN_ENV}"$'\n'"${var}=${digest}"
  DIGEST_ENVS+=("${var}=${digest}")
done

# 2c. Validate the full compose config LOCALLY with the pinned digests before we
#     touch the server (catches overlay/env mistakes without a round-trip).
echo "==> Validating compose config with pinned digests ..."
( cd "$REPO_ROOT/infra" && env "${DIGEST_ENVS[@]}" IMAGE_TAG="$TAG" \
    docker compose --env-file "$ENV_FILE" "${COMPOSE[@]}" config -q ) || {
  echo "ERROR: compose config is invalid with the pinned digests." >&2; exit 1; }

# 3. Provision the server (idempotent).
echo "==> Provisioning ${TARGET} ..."
ssh_ "mkdir -p ${REMOTE_DIR}"
rsync -az -e "ssh ${SSH_OPTS[*]}" \
  "$REPO_ROOT/infra/scripts/server-setup.sh" "${TARGET}:${REMOTE_DIR}/server-setup.sh"
ssh_ "bash ${REMOTE_DIR}/server-setup.sh"

# 4. Ship infra/ config (NOT source; images come from GHCR) + the cloud env file,
#    then inject the digest pins (strip any stale pins first, so redeploys and
#    rollbacks are idempotent).
echo "==> Syncing infra/ config + env (IMAGE_TAG=${TAG:0:12}) ..."
rsync -az --delete -e "ssh ${SSH_OPTS[*]}" \
  --exclude '.env' --exclude '.env.*' \
  "$REPO_ROOT/infra/" "${TARGET}:${REMOTE_DIR}/infra/"
rsync -az -e "ssh ${SSH_OPTS[*]}" "$ENV_FILE" "${TARGET}:${REMOTE_DIR}/infra/.env"

PIN_KEYS="IMAGE_TAG"
for svc in "${SERVICES[@]}"; do
  PIN_KEYS="${PIN_KEYS}|$(printf '%s' "$svc" | tr '[:lower:]' '[:upper:]')_IMAGE_DIGEST"
done
printf '%s\n' "$PIN_ENV" | ssh_ "cd ${REMOTE_DIR}/infra \
      && sed -i -E '/^(${PIN_KEYS})=/d' .env \
      && cat >> .env \
      && chmod 600 .env"

# 5. Pull pinned images and (re)start. --no-build guarantees nothing builds on prod.
echo "==> Pulling images + starting stack ..."
ssh_ "cd ${REMOTE_DIR}/infra && docker compose ${COMPOSE[*]} pull && docker compose ${COMPOSE[*]} up -d --no-build --remove-orphans"

# 5b. Apply Caddyfile changes. `up -d` only recreates containers whose compose
#     definition changed — edits to the bind-mounted Caddyfile are invisible to
#     it. `caddy reload` is Caddy's graceful zero-downtime reload (a no-op when
#     the config is unchanged), so running it every deploy is safe.
echo "==> Reloading Caddy config ..."
ssh_ "cd ${REMOTE_DIR}/infra && docker compose ${COMPOSE[*]} exec -T -w /etc/caddy caddy caddy reload --config /etc/caddy/Caddyfile"

# 5c. Closed-loop verification: `up -d` only proves compose accepted the config,
#     not that every container runs the new build (a partially failed pull leaves
#     the previous generation running). Compare each running container's OCI
#     revision label (stamped by CD) against the commit just deployed. Images
#     built before revision-labeling existed carry no label — warn but don't
#     fail, so rollbacks to old commits stay possible.
echo "==> Verifying running containers carry revision ${TAG:0:12} ..."
ssh_ "bash -s -- '${TAG}' '${REMOTE_DIR}'" <<'EOSH'
set -u
TAG="$1"; REMOTE_DIR="$2"
cd "${REMOTE_DIR}/infra"
fail=0
for s in profile-service job-service discovery-service agent-service notification-service frontend; do
  cid="$(docker compose -f docker-compose.yml -f docker-compose.prod.yml ps -q "$s")"
  if [ -z "$cid" ]; then
    echo "    ${s}: ERROR — no running container"; fail=1; continue
  fi
  rev="$(docker inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$cid")"
  if [ -z "$rev" ]; then
    echo "    ${s}: WARNING — image has no revision label (predates labeling)"
  elif [ "$rev" != "$TAG" ]; then
    echo "    ${s}: ERROR — running revision ${rev}, expected ${TAG}"; fail=1
  else
    echo "    ${s}: ${rev:0:12} ok"
  fi
done
exit "$fail"
EOSH

# 6. Prune superseded images. Each digest-pinned deploy strands the previous
#    generation (~3.7GB across the 6 app images) and nothing else ever deletes
#    it — unbounded growth until the disk fills. Keep the last 72h of unused
#    images for instant local rollback; older rollbacks re-pull from GHCR.
echo "==> Pruning images unused for >72h ..."
ssh_ "docker image prune -af --filter 'until=72h' | tail -1"

SERVER_HOST="$(grep -E '^SERVER_HOST=' "$ENV_FILE" | cut -d= -f2-)"
echo ""
echo "==> Deploy complete (commit ${TAG:0:12})."
echo "    Frontend : https://${SERVER_HOST}"
echo "    Keycloak : https://auth.${SERVER_HOST}"
echo "    Logs     : ssh ${TARGET} 'cd ${REMOTE_DIR}/infra && docker compose ${COMPOSE[*]} logs -f'"
