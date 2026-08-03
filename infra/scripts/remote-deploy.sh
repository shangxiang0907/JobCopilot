#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Deploy JobCopilot ON the server, from a checkout of the commit being deployed.
# Never run this from a developer machine — it assumes it IS the target host.
#
#   remote-deploy.sh <40-hex-commit-sha>
#
# Two callers, ONE implementation. The manual path (infra/scripts/deploy.sh, as
# root) and CD (the forced-command shim, as the unprivileged `deploy` user) both
# end up here, so an automated deploy and a hand-run deploy cannot drift apart.
#
# What this deliberately does NOT do, and why:
#   • Provision the host. That needs root and package installs; deploy.sh runs
#     server-setup.sh beforehand. CD must never need to install anything, so the
#     account CD logs in as never needs root.
#   • Write infra/.env. The production secrets live on this server and only ever
#     arrive through a manual, human-run deploy. CD does not carry them, which is
#     precisely what lets the CD key be restricted to "deploy <sha>" and nothing
#     else. Only the image digest pins are rewritten (step 3).
#
# Env vars:
#   GHCR_OWNER   (default: shangxiang0907) GHCR namespace owning the images
#   REMOTE_DIR   (default: /opt/jobcopilot) where the live compose project lives
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SHA="${1:?usage: remote-deploy.sh <40-hex-commit-sha>}"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: '${SHA}' is not a full 40-hex commit SHA." >&2; exit 2; }

GHCR_OWNER="${GHCR_OWNER:-shangxiang0907}"
REMOTE_DIR="${REMOTE_DIR:-/opt/jobcopilot}"
SERVICES=(profile job discovery agent notification frontend)
COMPOSE=(-f docker-compose.yml -f docker-compose.prod.yml)
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# 0. Serialize. Two overlapping deploys would interleave their digest pins in
#    .env and leave the stack running a mix of two commits. CD's concurrency
#    group only covers CD; a human running deploy.sh at the same moment is
#    exactly the case that group cannot see.
mkdir -p "$REMOTE_DIR"
exec 9>"${REMOTE_DIR}/.deploy.lock"
flock -n 9 || {
  echo "ERROR: another deploy holds ${REMOTE_DIR}/.deploy.lock. Wait for it." >&2
  exit 3
}

# 1. The checkout must BE the commit we were asked to deploy. Without this a
#    stale working tree would silently ship yesterday's config under today's SHA.
head_sha="$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null || true)"
if [ "$head_sha" != "$SHA" ]; then
  echo "ERROR: checkout at ${REPO_DIR} is ${head_sha:-<not a git repo>}," >&2
  echo "       but this deploy is for ${SHA}." >&2
  exit 4
fi

# The shim lives outside the repo (/usr/local/bin) so it survives checkouts —
# which also means it can fall behind. Warn rather than fail: a stale shim still
# works, it just may lack a fix, and failing here would block deploying the very
# commit that updates it.
SHIM_INSTALLED="/usr/local/bin/jobcopilot-deploy"
if [ -f "$SHIM_INSTALLED" ] && \
   ! cmp -s "$REPO_DIR/infra/scripts/jobcopilot-deploy" "$SHIM_INSTALLED"; then
  echo "WARNING: ${SHIM_INSTALLED} differs from this commit's copy —" >&2
  echo "         reinstall it (see infra/scripts/jobcopilot-deploy header)." >&2
fi

echo "==> Deploying ${SHA:0:12} on $(hostname) as $(id -un)"

# 2. Ship this commit's infra/ config into the live project dir. Deploying a
#    commit means deploying ITS compose files and Caddyfile, not whatever was
#    there before. .env is excluded — it is server-owned state (see header).
echo "==> Syncing infra/ config from the ${SHA:0:12} checkout ..."
rsync -a --delete --exclude '.env' --exclude '.env.*' \
  "${REPO_DIR}/infra/" "${REMOTE_DIR}/infra/"

[ -f "${REMOTE_DIR}/infra/.env" ] || {
  echo "ERROR: ${REMOTE_DIR}/infra/.env is missing. It holds the production" >&2
  echo "       secrets and is only ever installed by a manual deploy.sh run." >&2
  exit 5
}

# 3. Resolve every image tag to its IMMUTABLE digest, then pin the overlay to
#    <image>@sha256:... A tag can be moved; a digest cannot. GHCR packages are
#    public, so no registry login is needed.
echo "==> Resolving image digests for ${SHA:0:12} (owner: ${GHCR_OWNER}) ..."
PIN_ENV="IMAGE_TAG=${SHA}"
for svc in "${SERVICES[@]}"; do
  ref="ghcr.io/${GHCR_OWNER}/jobcopilot-${svc}:${SHA}"
  # Retry: right after CD pushes, GHCR manifest propagation has been observed to
  # exceed 20s. `|| true` keeps a failed inspect from killing the script inside
  # the substitution, which would skip the diagnostic below.
  digest=""
  for attempt in 1 2 3 4 5 6; do
    digest="$(docker buildx imagetools inspect "$ref" 2>/dev/null \
                | awk '/^Digest:/{print $2; exit}' || true)"
    [ -n "$digest" ] && break
    [ "$attempt" -lt 6 ] && {
      echo "    ${ref##*/}: not resolvable yet, retrying in 20s ..." >&2; sleep 20; }
  done
  if [ -z "$digest" ]; then
    echo "ERROR: could not resolve a digest for ${ref}." >&2
    echo "       Did CD finish building and pushing ${SHA:0:12} to GHCR?" >&2
    exit 6
  fi
  var="$(printf '%s' "$svc" | tr '[:lower:]' '[:upper:]')_IMAGE_DIGEST"
  echo "    jobcopilot-${svc} -> ${digest}"
  PIN_ENV="${PIN_ENV}"$'\n'"${var}=${digest}"
done

# Strip any previous pins before appending, so redeploys and rollbacks are
# idempotent instead of accumulating dead lines.
PIN_KEYS="IMAGE_TAG"
for svc in "${SERVICES[@]}"; do
  PIN_KEYS="${PIN_KEYS}|$(printf '%s' "$svc" | tr '[:lower:]' '[:upper:]')_IMAGE_DIGEST"
done
cd "${REMOTE_DIR}/infra"
sed -i -E "/^(${PIN_KEYS})=/d" .env
printf '%s\n' "$PIN_ENV" >> .env
chmod 600 .env

# 4. Validate the fully-resolved config BEFORE touching the running stack, so an
#    overlay or env mistake fails while production is still healthy.
echo "==> Validating compose config with pinned digests ..."
docker compose "${COMPOSE[@]}" config -q || {
  echo "ERROR: compose config is invalid with the pinned digests." >&2; exit 7; }

# 5. Pull and (re)start. --no-build guarantees nothing is ever built here.
echo "==> Pulling images + starting stack ..."
docker compose "${COMPOSE[@]}" pull
docker compose "${COMPOSE[@]}" up -d --no-build --remove-orphans

# 5b. `up -d` only recreates containers whose compose definition changed, so
#     edits to the bind-mounted Caddyfile are invisible to it. `caddy reload` is
#     a graceful zero-downtime reload and a no-op when the config is unchanged.
echo "==> Reloading Caddy config ..."
docker compose "${COMPOSE[@]}" exec -T -w /etc/caddy caddy \
  caddy reload --config /etc/caddy/Caddyfile

# 5c. Closed-loop verification. `up -d` proves compose accepted the config, not
#     that every container runs the new build — a partially failed pull leaves
#     the previous generation running. Compare each container's OCI revision
#     label (stamped by CD) against the commit we just deployed.
echo "==> Verifying running containers carry revision ${SHA:0:12} ..."
fail=0
for s in profile-service job-service discovery-service agent-service \
         notification-service frontend; do
  cid="$(docker compose "${COMPOSE[@]}" ps -q "$s")"
  if [ -z "$cid" ]; then
    echo "    ${s}: ERROR — no running container"; fail=1; continue
  fi
  rev="$(docker inspect --format \
          '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$cid")"
  if [ -z "$rev" ]; then
    # Images built before revision-labeling existed carry no label. Warn, don't
    # fail, so rolling back to an old commit stays possible.
    echo "    ${s}: WARNING — image has no revision label (predates labeling)"
  elif [ "$rev" != "$SHA" ]; then
    echo "    ${s}: ERROR — running revision ${rev}, expected ${SHA}"; fail=1
  else
    echo "    ${s}: ${rev:0:12} ok"
  fi
done
[ "$fail" -eq 0 ] || {
  echo "ERROR: deploy did not converge on ${SHA:0:12}." >&2; exit 8; }

# 6. Each digest-pinned deploy strands the previous generation (~3.7GB across
#    the 6 app images) and nothing else ever deletes it — unbounded growth until
#    the disk fills. Keep 72h for instant local rollback; older ones re-pull.
echo "==> Pruning images unused for >72h ..."
docker image prune -af --filter 'until=72h' | tail -1

SERVER_HOST="$(grep -E '^SERVER_HOST=' "${REMOTE_DIR}/infra/.env" | cut -d= -f2-)"
echo ""
echo "==> Deploy complete (commit ${SHA:0:12})."
echo "    Frontend : https://${SERVER_HOST}"
echo "    Keycloak : https://auth.${SERVER_HOST}"
