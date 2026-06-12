#!/usr/bin/env bash
# Smoke test for the local JobCopilot dev environment.
#
# Three independent concerns are tested separately:
#   1. Infrastructure  — TCP reachability of each backing service
#   2. Service health  — direct /healthz/ready on each app service (bypass Kong)
#   3. Kong routing    — route config verified via Kong admin API
#   4. E2E proxy       — GET /healthz/{service} through Kong → service → 200
#   5. Management UIs  — Keycloak, Temporal UI, Frontend
#
# Port reference (mirrors docker-compose.yml; update here if compose changes):
#   Kong proxy          :8000     Kong admin          :8001
#   Keycloak            :8080     RabbitMQ UI         :15672
#   Temporal UI         :8233     Frontend            :3000
#   profile-service     :8010     job-service         :8011
#   discovery-service   :8012     agent-service       :8013
#   notification-svc    :8014
#
# Expected Kong routes (mirrors infra/kong/kong.yml; update here if kong.yml changes):
#   API routes:    profile-routes, job-routes, discovery-routes,
#                  agent-routes, notification-routes
#   Health routes: profile-health-route, job-health-route, discovery-health-route,
#                  agent-health-route, notification-health-route

set -euo pipefail

# ── colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

PASS=0
FAIL=0

pass() { echo -e "  ${GREEN}✓${NC} $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}✗${NC} $1"; FAIL=$((FAIL + 1)); }
section() { echo -e "\n${YELLOW}▶ $1${NC}"; }

# ── helpers ───────────────────────────────────────────────────────────────────

http_check() {
    local label="$1" url="$2" expected="$3"
    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 --max-time 5 "$url" 2>/dev/null || echo "000")
    if echo "$expected" | tr ',' '\n' | grep -qx "$status"; then
        pass "$label  →  HTTP $status"
    else
        fail "$label  →  HTTP $status  (expected $expected)"
    fi
}

tcp_check() {
    local label="$1" host="$2" port="$3"
    if bash -c "exec 3<>/dev/tcp/$host/$port" 2>/dev/null; then
        pass "$label  →  TCP $host:$port reachable"
    else
        fail "$label  →  TCP $host:$port unreachable"
    fi
}

# Verifies a named Kong route exists by querying the admin API.
# Fails clearly if Kong is unreachable or the route name is absent.
kong_route_exists() {
    local label="$1" route_name="$2"
    local routes
    routes=$(curl -s --connect-timeout 3 --max-time 5 \
        "http://localhost:8001/routes?size=100" 2>/dev/null \
        | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    names = [r.get('name','') for r in data.get('data', [])]
    print('\n'.join(names))
except Exception:
    pass
" 2>/dev/null || true)

    if [ -z "$routes" ]; then
        fail "$label  →  Kong admin API unreachable"
    elif echo "$routes" | grep -qx "$route_name"; then
        pass "$label  →  route '$route_name' configured"
    else
        fail "$label  →  route '$route_name' NOT found in Kong"
    fi
}

# ── 1. Infrastructure ─────────────────────────────────────────────────────────
section "Infrastructure"
tcp_check  "PostgreSQL"       localhost 5432
tcp_check  "Redis"            localhost 6379
tcp_check  "RabbitMQ (AMQP)" localhost 5672
http_check "RabbitMQ UI"      "http://localhost:15672"  "200"
tcp_check  "Qdrant"           localhost 6333
tcp_check  "Temporal gRPC"    localhost 7233

# ── 2. Service health (direct, bypass Kong) ───────────────────────────────────
section "Service health — /healthz/ready (direct, bypasses Kong)"
http_check "profile-service    :8010" "http://localhost:8010/healthz/ready" "200"
http_check "job-service        :8011" "http://localhost:8011/healthz/ready" "200"
http_check "discovery-service  :8012" "http://localhost:8012/healthz/ready" "200"
http_check "agent-service      :8013" "http://localhost:8013/healthz/ready" "200"
http_check "notification-svc   :8014" "http://localhost:8014/healthz/ready" "200"

# ── 3. Kong routing config (admin API) ───────────────────────────────────────
section "Kong routing config — verified via admin API (:8001)"
kong_route_exists "profile API route"      "profile-routes"
kong_route_exists "job API route"          "job-routes"
kong_route_exists "discovery API route"    "discovery-routes"
kong_route_exists "agent API route"        "agent-routes"
kong_route_exists "notification API route" "notification-routes"
kong_route_exists "profile health route"   "profile-health-route"
kong_route_exists "job health route"       "job-health-route"
kong_route_exists "discovery health route" "discovery-health-route"
kong_route_exists "agent health route"     "agent-health-route"
kong_route_exists "notification health"    "notification-health-route"

# ── 4. End-to-end through Kong proxy ─────────────────────────────────────────
section "End-to-end — GET /healthz/{service} via Kong proxy (:8000)"
http_check "profile-service"     "http://localhost:8000/healthz/profile-service"     "200"
http_check "job-service"         "http://localhost:8000/healthz/job-service"         "200"
http_check "discovery-service"   "http://localhost:8000/healthz/discovery-service"   "200"
http_check "agent-service"       "http://localhost:8000/healthz/agent-service"       "200"
http_check "notification-svc"    "http://localhost:8000/healthz/notification-service" "200"

# ── 5. Management UIs ─────────────────────────────────────────────────────────
section "Management UIs"
http_check "Keycloak health"  "http://localhost:8080/health/ready"  "200"
http_check "Temporal UI"      "http://localhost:8233"               "200"
http_check "Frontend"         "http://localhost:3000"               "200,307"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────"
TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then
    echo -e "${GREEN}All $TOTAL checks passed.${NC}"
else
    echo -e "${RED}$FAIL/$TOTAL checks failed.${NC}"
fi
echo "────────────────────────────────────────"

[ "$FAIL" -eq 0 ]
