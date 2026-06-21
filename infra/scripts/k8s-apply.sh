#!/usr/bin/env bash
# k8s-apply.sh — Apply all JobCopilot K8s manifests in dependency order.
#
# Usage:
#   ./infra/scripts/k8s-apply.sh [--dry-run]
#
# Prerequisites:
#   - kubectl configured and pointing at the target cluster
#   - Sealed Secrets controller installed (infra/scripts/seal-secrets.sh install)
#   - KEDA installed (https://keda.sh/docs/latest/deploy/)
#   - sealed-secrets/sealed-secrets.yaml generated (seal-secrets.sh seal)
#
# The script applies in three phases so K8s has time to create CRDs and
# namespace-scoped resources before Deployments reference them.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
K8S="${REPO_ROOT}/infra/k8s"

DRY_RUN=""
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN="--dry-run=client"
  echo "==> DRY RUN mode — no changes will be applied"
fi

_apply() {
  echo "==> Applying: $*"
  kubectl apply ${DRY_RUN} -f "$@"
}

_wait_rollout() {
  if [[ -n "${DRY_RUN}" ]]; then return; fi
  local resource=$1
  echo "==> Waiting for rollout: ${resource}"
  kubectl rollout status "${resource}" -n jobcopilot --timeout=5m
}

# ── Phase 1: Namespace + Config + Secrets ────────────────────────────────────
echo ""
echo "── Phase 1: Namespace, ConfigMaps, Secrets ──"
_apply "${K8S}/namespace.yaml"
_apply "${K8S}/config/configmap.yaml"
_apply "${K8S}/config/keycloak-realm-configmap.yaml"
_apply "${K8S}/sealed-secrets/sealed-secrets.yaml"

# ── Phase 2: Infrastructure (stateful dependencies) ──────────────────────────
echo ""
echo "── Phase 2: Infrastructure ──"
_apply "${K8S}/infra/postgres.yaml"
_apply "${K8S}/infra/redis.yaml"
_apply "${K8S}/infra/rabbitmq.yaml"
_apply "${K8S}/infra/qdrant.yaml"

if [[ -z "${DRY_RUN}" ]]; then
  echo "==> Waiting for postgres StatefulSet..."
  kubectl rollout status statefulset/postgres -n jobcopilot --timeout=5m
fi

_apply "${K8S}/infra/keycloak.yaml"
_apply "${K8S}/infra/temporal.yaml"
_apply "${K8S}/infra/temporal-ui.yaml"

if [[ -z "${DRY_RUN}" ]]; then
  echo "==> Waiting for Keycloak and Temporal..."
  kubectl rollout status deployment/keycloak -n jobcopilot --timeout=5m
  kubectl rollout status deployment/temporal  -n jobcopilot --timeout=5m
fi

# Init jobs run once and succeed; re-applying is idempotent (Job already exists).
_apply "${K8S}/infra/keycloak-init-job.yaml"
_apply "${K8S}/infra/temporal-init-job.yaml"

# ── Phase 3: Gateway + Application Services + Network Policies ───────────────
echo ""
echo "── Phase 3: Gateway, Services, Network Policies ──"
_apply "${K8S}/gateway/kong.yaml"
_apply "${K8S}/gateway/cert-issuer.yaml"
_apply "${K8S}/gateway/ingress.yaml"
_apply "${K8S}/services/profile.yaml"
_apply "${K8S}/services/job.yaml"
_apply "${K8S}/services/discovery.yaml"
_apply "${K8S}/services/agent.yaml"
_apply "${K8S}/services/notification.yaml"
_apply "${K8S}/services/frontend.yaml"
_apply "${K8S}/network-policy.yaml"

if [[ -z "${DRY_RUN}" ]]; then
  echo ""
  echo "── Waiting for all Deployments to become ready ──"
  for deploy in kong profile-service job-service discovery-service agent-service notification-service frontend; do
    kubectl rollout status deployment/"${deploy}" -n jobcopilot --timeout=5m
  done
fi

echo ""
echo "✓ All resources applied successfully."
