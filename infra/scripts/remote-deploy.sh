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

# The shim is the security boundary for the CD key, and it lives outside the
# repo (/usr/local/bin, root-owned) so it survives checkouts — which also means
# it can fall behind the repo. Drift FAILS the deploy rather than warning.
#
# It is deliberately NOT auto-installed from here or from deploy.sh. A security
# control must change deliberately, visibly and rarely; refreshing it as a side
# effect of every routine deploy would mean nobody ever notices it changed. The
# shim belongs to the same category as the deploy user, the authorized_keys
# entry and the firewall rules — host provisioning, done by hand, once.
#
# Failing therefore forces the correct order for a shim change: install it, THEN
# deploy the commit that carries it. The override exists for the one case that
# order cannot serve — rolling back to an older commit whose shim differs — and
# is reachable only from a real shell (i.e. root), because the CD key cannot
# pass environment variables through the shim.
SHIM_INSTALLED="/usr/local/bin/jobcopilot-deploy"
SHIM_REPO="${REPO_DIR}/infra/scripts/jobcopilot-deploy"
if [ "${JOBCOPILOT_SHIM_DRIFT:-enforce}" != "enforce" ]; then
  echo "WARNING: shim drift check SKIPPED by JOBCOPILOT_SHIM_DRIFT=${JOBCOPILOT_SHIM_DRIFT}." >&2
elif [ ! -f "$SHIM_INSTALLED" ]; then
  echo "ERROR: ${SHIM_INSTALLED} is not installed — the CD key has no gate." >&2
  echo "       From a checkout of this commit, as root:" >&2
  echo "         scp infra/scripts/jobcopilot-deploy <host>:${SHIM_INSTALLED}" >&2
  echo "         ssh <host> 'chown root:root ${SHIM_INSTALLED} && chmod 755 ${SHIM_INSTALLED}'" >&2
  exit 10
elif ! cmp -s "$SHIM_REPO" "$SHIM_INSTALLED"; then
  echo "ERROR: the installed shim differs from this commit's copy." >&2
  echo "       Install it first, then deploy this commit again (docs/DEPLOYMENT.md §5)." >&2
  echo "       For a rollback to an older shim, re-run as root with" >&2
  echo "       JOBCOPILOT_SHIM_DRIFT=allow." >&2
  exit 10
fi

# 1b. Supply-chain gate, enforced HERE because this is where the decision is
#     actually made. deploy.sh checks the same thing client-side, but a client
#     check only protects callers who run the client — and the whole point of
#     the forced-command shim is that anyone holding the CD key can invoke this
#     directly. CD pushes images BEFORE scanning them, so a commit whose Trivy
#     scan found a Critical CVE still has perfectly pullable images: resolving a
#     digest proves an image exists, never that it should be trusted.
#
#     Checked per-JOB rather than per-run, and that distinction is load-bearing:
#     when CD itself calls us, the deploy job is part of the very run we are
#     asking about, so that run can never be "completed" while we look at it.
#     The gating jobs (build, E2E, image scan) HAVE concluded by then — they are
#     the deploy job's `needs` — so their conclusions are the honest signal.
#
#     The repo is public, so this needs no credentials. Unreachable API fails
#     CLOSED; JOBCOPILOT_CD_GATE=skip overrides for an emergency rollback during
#     a GitHub outage. That override is only settable from a real shell, i.e. by
#     root — the CD key cannot pass environment variables through the shim.
CD_GATE="${JOBCOPILOT_CD_GATE:-enforce}"
if [ "$CD_GATE" != "enforce" ]; then
  echo "WARNING: CD supply-chain gate SKIPPED by JOBCOPILOT_CD_GATE=${CD_GATE}." >&2
  echo "         Images for ${SHA:0:12} may never have passed the Trivy scan." >&2
else
  echo "==> Verifying the CD gating jobs for ${SHA:0:12} went green ..."
  verdict="$(python3 - "$SHA" <<'PY'
import json, sys, urllib.request

REPO = "shangxiang0907/JobCopilot"
# The deploy job's `needs`, by display-name prefix (they are matrix jobs).
GATING = ("Build & Push", "E2E Smoke", "Image Scan")
sha = sys.argv[1]


def get(url):
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "jobcopilot-deploy"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


try:
    runs = get(f"https://api.github.com/repos/{REPO}/actions/runs?head_sha={sha}&per_page=100")
    cd_runs = [r for r in runs["workflow_runs"] if r.get("name") == "CD"]
    if not cd_runs:
        print("missing no CD workflow run exists for this commit")
        raise SystemExit(0)
    # Latest attempt wins, so a re-run after a fix is what counts.
    run = max(cd_runs, key=lambda r: r["run_number"])
    jobs = get(f"https://api.github.com/repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=100")
except Exception as exc:  # noqa: BLE001 - any failure to ASK must not read as a pass
    print(f"unavailable {type(exc).__name__}: {exc}")
    raise SystemExit(0)

gating = [j for j in jobs["jobs"] if j["name"].startswith(GATING)]
if not gating:
    print(f"missing run {run['id']} has not started its gating jobs")
elif bad := [f"{j['name']}={j['status']}/{j['conclusion']}" for j in gating if j["conclusion"] != "success"]:
    print("failed " + ", ".join(bad[:4]))
else:
    print(f"ok {len(gating)} gating jobs green in run {run['id']}")
PY
)" || verdict="unavailable python3 failed"

  case "$verdict" in
    ok\ *)
      echo "    ${verdict#ok }" ;;
    failed\ *)
      echo "ERROR: CD gating jobs for ${SHA:0:12} did not pass: ${verdict#failed }" >&2
      echo "       Its images may carry a Critical CVE. Refusing to deploy." >&2
      exit 9 ;;
    missing\ *)
      echo "ERROR: ${verdict#missing } (${SHA:0:12})." >&2
      echo "       Only commits CD has built and scanned may be deployed." >&2
      exit 9 ;;
    *)
      echo "ERROR: could not reach the GitHub API to verify the CD run:" >&2
      echo "       ${verdict#unavailable }" >&2
      echo "       Failing closed. For an emergency rollback during a GitHub" >&2
      echo "       outage, re-run as root with JOBCOPILOT_CD_GATE=skip." >&2
      exit 9 ;;
  esac
fi

# 1d. Monotonicity: refuse to move production BACKWARDS unless asked to.
#
#     Every other gate passes for an older commit — it is an ancestor of main,
#     its CD jobs are green, and the revision check at the end confirms the
#     containers match what was requested. None of them asks whether the commit
#     is newer than what is already running, so a backward deploy looks
#     completely healthy in the logs.
#
#     Two realistic ways to get there, both accidents rather than attacks:
#     approving a CD run that has been sitting in the queue while production
#     moved on (GitHub's concurrency group serializes CD runs, but it cannot see
#     a manual deploy.sh run at all), and running deploy.sh from a local main
#     that is behind origin.
#
#     Migrations are what make this expensive rather than merely surprising:
#     containers run `alembic upgrade head` at startup and alembic never goes
#     backwards, so old code meets a newer schema. v0.3's is_active -> is_default
#     rename is exactly that shape — the old code queries a column that no longer
#     exists, and Profile Service crash-loops.
#
#     Rollback stays fully supported, it just has to be deliberate:
#     JOBCOPILOT_ALLOW_ROLLBACK=1 (root-only, like the other overrides —
#     deploy.sh forwards it when invoked with ROLLBACK=1).
#
#     KNOWN LIMIT, and it applies to every check in this file: the shim runs the
#     copy of this script that ships WITH the commit being deployed, so
#     deploying a commit older than a given check simply runs a version that
#     never had it. The accidents this gate exists for are covered — a queued CD
#     approval and a behind-origin deploy.sh both name a recent commit — but
#     rolling back far enough steps outside all of them. The only
#     version-independent enforcement point is the shim itself; keeping these
#     checks here instead is the deliberate trade for a small, rarely-changed
#     boundary (ADR-010).
#     Read the running revision the same way step 5c does — through compose,
#     not `docker ps --format {{.Image}}`: digest-pinned containers report a
#     short image ID there, so a name-prefix match silently finds nothing and
#     the whole gate becomes a no-op. Third-party images (keycloak, for one)
#     also set org.opencontainers.image.revision to THEIR upstream commit, so
#     "first container carrying the label" is wrong too. Several services are
#     tried because any single one may be momentarily absent.
current_rev=""
if [ -f "${REMOTE_DIR}/infra/docker-compose.yml" ]; then
  for s in frontend job-service profile-service; do
    cid="$( ( cd "${REMOTE_DIR}/infra" && docker compose "${COMPOSE[@]}" ps -q "$s" ) 2>/dev/null || true )"
    [ -n "$cid" ] || continue
    current_rev="$(docker inspect --format \
      '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$cid" 2>/dev/null || true)"
    [ -n "$current_rev" ] && break
  done
fi
if [ "${JOBCOPILOT_ALLOW_ROLLBACK:-0}" = "1" ]; then
  echo "==> Rollback explicitly allowed (JOBCOPILOT_ALLOW_ROLLBACK=1)."
elif [ -z "$current_rev" ]; then
  echo "==> No JobCopilot containers running — nothing to move backwards from."
elif [ "$current_rev" = "$SHA" ]; then
  echo "==> Already running ${SHA:0:12}; redeploying the same commit."
elif ! git -C "$REPO_DIR" cat-file -e "${current_rev}^{commit}" 2>/dev/null; then
  # The running revision is not in the repo at all, which means history was
  # rewritten under it. Direction is genuinely undecidable, and refusing would
  # strand the host until someone overrode every deploy, so continue — loudly.
  echo "WARNING: the running revision ${current_rev:0:12} no longer exists in the" >&2
  echo "         repository (history rewritten?). Cannot tell whether this deploy" >&2
  echo "         moves forwards or backwards. Continuing." >&2
elif git -C "$REPO_DIR" merge-base --is-ancestor "$SHA" "$current_rev"; then
  echo "ERROR: ${SHA:0:12} is an ANCESTOR of the running ${current_rev:0:12} —" >&2
  echo "       this deploy would move production backwards." >&2
  echo "       Schema migrations only go forwards, so older code would meet a" >&2
  echo "       newer database. If you mean to roll back, say so explicitly:" >&2
  echo "         deploy.sh  ->  ROLLBACK=1 GIT_REF=${SHA:0:12} ... ./infra/scripts/deploy.sh" >&2
  echo "         by hand    ->  JOBCOPILOT_ALLOW_ROLLBACK=1 (as root)" >&2
  echo "       If instead an old CD approval is queued, cancel that run." >&2
  exit 11
else
  echo "==> Moving forwards: ${current_rev:0:12} -> ${SHA:0:12}."
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
