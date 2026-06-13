#!/usr/bin/env bash
# update-kong-jwt-key.sh — Fetch Keycloak's RS256 public key and patch the Kong ConfigMap.
#
# Usage:
#   # For Kubernetes (kubectl must be configured):
#   ./infra/scripts/update-kong-jwt-key.sh k8s [--keycloak-url http://keycloak:8080]
#
#   # For Docker Compose (regenerates kong.yml and restarts Kong):
#   ./infra/scripts/update-kong-jwt-key.sh compose [--keycloak-url http://localhost:8080]
#
# Prerequisites:
#   - curl, python3 (for JWK→PEM conversion)
#   - kubectl (for k8s mode)
#   - docker compose (for compose mode)
#
# What it does:
#   1. Fetches JWKS from Keycloak's well-known endpoint
#   2. Extracts the active RS256 public key (use=sig, kty=RSA)
#   3. Converts JWK → PEM format
#   4. Patches the kong-config ConfigMap / kong.yml with the real key
#   5. Triggers a rolling restart of Kong

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REALM="jobcopilot"
NAMESPACE="jobcopilot"
CONFIGMAP_NAME="kong-config"
KONG_YAML="${REPO_ROOT}/infra/k8s/gateway/kong.yaml"

KEYCLOAK_URL="http://localhost:8080"
MODE="${1:-}"

# ---------------------------------------------------------------------------
_require() {
  if ! command -v "$1" &>/dev/null; then
    echo "ERROR: '$1' not found. Please install it." >&2
    exit 1
  fi
}

fetch_public_key_pem() {
  local url="${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/certs"
  echo "==> Fetching JWKS from ${url} ..." >&2

  local jwks
  jwks="$(curl -sf "${url}")"

  # Extract the first RS256 signing key using python3
  python3 - <<PYTHON
import json, base64, struct, sys

jwks = json.loads('''${jwks}''')
key = next(
    (k for k in jwks.get("keys", [])
     if k.get("kty") == "RSA" and k.get("use") == "sig" and k.get("alg", "RS256") == "RS256"),
    None,
)
if not key:
    print("ERROR: No RS256 signing key found in JWKS", file=sys.stderr)
    sys.exit(1)

def b64url_to_int(s):
    s += "=" * (4 - len(s) % 4)
    return int.from_bytes(base64.urlsafe_b64decode(s), "big")

n = b64url_to_int(key["n"])
e = b64url_to_int(key["e"])

# Encode modulus and exponent as DER SubjectPublicKeyInfo
def encode_length(length):
    if length < 0x80:
        return bytes([length])
    n_bytes = (length.bit_length() + 7) // 8
    return bytes([0x80 | n_bytes]) + length.to_bytes(n_bytes, "big")

def encode_int(value):
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    if raw[0] >= 0x80:
        raw = b"\x00" + raw
    return b"\x02" + encode_length(len(raw)) + raw

# RSAPublicKey ::= SEQUENCE { modulus INTEGER, publicExponent INTEGER }
rsa_key = b"\x30" + encode_length(len(encode_int(n)) + len(encode_int(e))) + encode_int(n) + encode_int(e)

# AlgorithmIdentifier for rsaEncryption
algo_id = bytes.fromhex("300d06092a864886f70d0101010500")

# SubjectPublicKeyInfo ::= SEQUENCE { algorithm, subjectPublicKey BIT STRING }
bit_string = b"\x03" + encode_length(len(rsa_key) + 1) + b"\x00" + rsa_key
spki = b"\x30" + encode_length(len(algo_id) + len(bit_string)) + algo_id + bit_string

pem = base64.encodebytes(spki).decode().strip()
lines = [pem[i:i+64] for i in range(0, len(pem), 64)]
print("-----BEGIN PUBLIC KEY-----")
print("\n".join(lines))
print("-----END PUBLIC KEY-----")
PYTHON
}

# ---------------------------------------------------------------------------
cmd_k8s() {
  _require curl
  _require python3
  _require kubectl

  local pub_key
  pub_key="$(fetch_public_key_pem)"

  echo "==> Public key fetched (${#pub_key} chars). Patching ConfigMap ${CONFIGMAP_NAME} ..."

  # Read current kong.yml from the ConfigMap, replace placeholder, re-apply
  local current_yml
  current_yml="$(kubectl -n "${NAMESPACE}" get configmap "${CONFIGMAP_NAME}" -o jsonpath='{.data.kong\.yml}')"

  # Replace everything between -----BEGIN PUBLIC KEY----- and -----END PUBLIC KEY----- markers
  local new_yml
  new_yml="$(python3 - <<PYTHON
import re, sys

current = """${current_yml}"""
pub_key = """${pub_key}"""

# Indent the key to match the YAML multiline literal block (14 spaces)
indent = " " * 14
indented = "\n".join(indent + line for line in pub_key.splitlines())

pattern = r'(-----BEGIN PUBLIC KEY-----\n).*?(-----END PUBLIC KEY-----)'
replacement = indented
new = re.sub(pattern, indented, current, flags=re.DOTALL)
print(new)
PYTHON
)"

  kubectl -n "${NAMESPACE}" create configmap "${CONFIGMAP_NAME}" \
    --from-literal="kong.yml=${new_yml}" \
    --dry-run=client -o yaml | kubectl apply -f -

  echo "==> ConfigMap updated. Triggering Kong rolling restart ..."
  kubectl -n "${NAMESPACE}" rollout restart deployment/kong
  kubectl -n "${NAMESPACE}" rollout status deployment/kong --timeout=120s
  echo "==> Done. Kong is now validating Keycloak RS256 JWTs."
}

# ---------------------------------------------------------------------------
cmd_compose() {
  _require curl
  _require python3

  local pub_key
  pub_key="$(fetch_public_key_pem)"

  echo "==> Public key fetched. Updating ${KONG_YAML} ..."

  python3 - <<PYTHON
import re, sys

with open("${KONG_YAML}") as f:
    content = f.read()

pub_key = """${pub_key}"""
indent = " " * 14
indented = "\n".join(indent + line for line in pub_key.splitlines())

pattern = r'(rsa_public_key: \|)(\n[ ]*)-----BEGIN PUBLIC KEY-----.*?-----END PUBLIC KEY-----'
new_block = "rsa_public_key: |\n" + indented
content = re.sub(pattern, new_block, content, flags=re.DOTALL)

with open("${KONG_YAML}", "w") as f:
    f.write(content)

print("Updated ${KONG_YAML}")
PYTHON

  echo "==> Restarting Kong container ..."
  docker compose -f "${REPO_ROOT}/infra/docker-compose.yml" restart kong
  echo "==> Done."
}

# ---------------------------------------------------------------------------
shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --keycloak-url) KEYCLOAK_URL="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

case "${MODE}" in
  k8s)     cmd_k8s ;;
  compose) cmd_compose ;;
  *)
    echo "Usage: $0 {k8s|compose} [--keycloak-url <url>]"
    exit 1
    ;;
esac
