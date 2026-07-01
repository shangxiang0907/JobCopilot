#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# One-time provisioning for a fresh Ubuntu 24.04 server. Idempotent.
# Runs ON the server — invoked remotely by deploy.sh. Does NOT start the stack
# (deploy.sh pulls images and brings it up after provisioning).
#
# Installs Docker from the official apt repo (auditable; preferred over curl|sh),
# a host firewall (ufw: 22/80/443 only), fail2ban, and key-only SSH.
#
# NOTE: for stronger edge protection, ALSO create a Hetzner Cloud Firewall
# (network level, outside the VM) with the same 22/80/443 rules — it cannot be
# bypassed by Docker's iptables rules the way a host firewall can.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "==> [1/4] Installing Docker (official apt repository) ..."
if ! command -v docker >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
fi

echo "==> [2/4] Installing fail2ban + ufw ..."
apt-get install -y -qq fail2ban ufw

echo "==> [3/4] Firewall: allow SSH + HTTP + HTTPS only ..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "==> [4/4] Hardening SSH (key-only auth) + enabling fail2ban ..."
cat > /etc/ssh/sshd_config.d/99-jobcopilot-hardening.conf <<'EOF'
PasswordAuthentication no
PermitRootLogin prohibit-password
EOF
systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || true
systemctl enable --now fail2ban

echo "==> Provisioning complete."
