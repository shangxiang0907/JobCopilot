#!/usr/bin/env bash
# seal-secrets.sh — Install Sealed Secrets controller and seal K8s secrets.
#
# Usage:
#   ./infra/scripts/seal-secrets.sh install   # Install controller into kube-system
#   ./infra/scripts/seal-secrets.sh seal       # Seal secrets.yaml → sealed-secrets.yaml
#   ./infra/scripts/seal-secrets.sh apply      # Apply sealed-secrets.yaml to cluster
#   ./infra/scripts/seal-secrets.sh rotate     # Re-seal after rotating secrets.yaml values
#
# Prerequisites:
#   - kubectl configured and pointing at target cluster
#   - helm >= 3 (for 'install' subcommand)
#   - kubeseal CLI (https://github.com/bitnami-labs/sealed-secrets/releases)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMPLATE="${REPO_ROOT}/infra/k8s/config/secrets.yaml.template"
SECRETS="${REPO_ROOT}/infra/k8s/config/secrets.yaml"
SEALED="${REPO_ROOT}/infra/k8s/sealed-secrets/sealed-secrets.yaml"
CONTROLLER_NS="kube-system"
CONTROLLER_NAME="sealed-secrets-controller"
HELM_REPO="https://bitnami-labs.github.io/sealed-secrets"

# ---------------------------------------------------------------------------
_require() {
  if ! command -v "$1" &>/dev/null; then
    echo "ERROR: '$1' not found. Please install it first." >&2
    exit 1
  fi
}

_controller_ready() {
  kubectl -n "${CONTROLLER_NS}" rollout status deployment/"${CONTROLLER_NAME}" --timeout=60s &>/dev/null
}

# ---------------------------------------------------------------------------
cmd_install() {
  _require helm
  _require kubectl

  echo "==> Adding Sealed Secrets Helm repo..."
  helm repo add sealed-secrets "${HELM_REPO}" --force-update
  helm repo update sealed-secrets

  echo "==> Installing sealed-secrets-controller into ${CONTROLLER_NS}..."
  helm upgrade --install "${CONTROLLER_NAME}" sealed-secrets/sealed-secrets \
    --namespace "${CONTROLLER_NS}" \
    --create-namespace \
    --set fullnameOverride="${CONTROLLER_NAME}" \
    --wait

  echo "==> Controller ready."
  echo ""
  echo "Next step: run './infra/scripts/seal-secrets.sh seal'"
}

# ---------------------------------------------------------------------------
cmd_seal() {
  _require kubeseal
  _require kubectl

  if [[ ! -f "${SECRETS}" ]]; then
    echo "ERROR: ${SECRETS} not found."
    echo "  1. Copy the template:  cp ${TEMPLATE} ${SECRETS}"
    echo "  2. Fill in all CHANGE_ME values."
    echo "  3. Re-run this command."
    exit 1
  fi

  # Verify no CHANGE_ME placeholders remain
  if grep -q "CHANGE_ME" "${SECRETS}"; then
    echo "ERROR: ${SECRETS} still contains CHANGE_ME placeholders."
    echo "  Fill in all values before sealing."
    exit 1
  fi

  if ! _controller_ready; then
    echo "ERROR: Sealed Secrets controller not ready in ${CONTROLLER_NS}."
    echo "  Run './infra/scripts/seal-secrets.sh install' first."
    exit 1
  fi

  echo "==> Sealing ${SECRETS} → ${SEALED} ..."
  kubeseal \
    --controller-name "${CONTROLLER_NAME}" \
    --controller-namespace "${CONTROLLER_NS}" \
    --format yaml \
    < "${SECRETS}" \
    > "${SEALED}"

  echo "==> Done. ${SEALED} is safe to commit."
  echo "  git add ${SEALED} && git commit -m 'chore(k8s): update sealed secrets'"
}

# ---------------------------------------------------------------------------
cmd_apply() {
  _require kubectl

  if ! grep -q "SealedSecret" "${SEALED}"; then
    echo "ERROR: ${SEALED} does not contain SealedSecret resources."
    echo "  Run './infra/scripts/seal-secrets.sh seal' first."
    exit 1
  fi

  echo "==> Applying ${SEALED} to cluster..."
  kubectl apply -f "${SEALED}"
  echo "==> Done."
}

# ---------------------------------------------------------------------------
cmd_rotate() {
  echo "==> Rotation workflow:"
  echo "  1. Edit ${SECRETS} with new values."
  echo "  2. Running seal..."
  cmd_seal
  echo ""
  echo "  3. Applying new sealed secrets..."
  cmd_apply
  echo ""
  echo "  4. Commit the updated sealed-secrets.yaml:"
  echo "     git add ${SEALED} && git commit -m 'chore(k8s): rotate secrets'"
}

# ---------------------------------------------------------------------------
case "${1:-help}" in
  install) cmd_install ;;
  seal)    cmd_seal ;;
  apply)   cmd_apply ;;
  rotate)  cmd_rotate ;;
  *)
    echo "Usage: $0 {install|seal|apply|rotate}"
    exit 1
    ;;
esac
