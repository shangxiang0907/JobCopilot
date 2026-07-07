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

echo "==> [1/6] Installing Docker (official apt repository) ..."
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

echo "==> [2/6] Configuring Docker daemon (log rotation + live-restore) ..."
# Without this, Docker's json-file logs grow UNBOUNDED — a crash-looping or
# chatty container eventually fills the disk and takes the node down. Loki only
# reads container logs (via the Docker API); it never truncates the source
# files, so rotation here is the only thing capping them. live-restore keeps
# containers running across dockerd restarts/upgrades.
# NOTE: log-opts apply to containers created AFTER this change — deploy.sh
# recreates the stack, so a normal deploy picks it up.
DAEMON_JSON='{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "20m",
    "max-file": "3"
  },
  "live-restore": true
}'
if [ "$(cat /etc/docker/daemon.json 2>/dev/null)" != "$DAEMON_JSON" ]; then
  printf '%s\n' "$DAEMON_JSON" > /etc/docker/daemon.json
  # log-opts are NOT SIGHUP-reloadable — the daemon must restart to serve the
  # new defaults. One-time ~15s container bounce on first application (restart
  # policies bring everything back); a no-op on every subsequent run.
  systemctl restart docker
fi

echo "==> [3/6] Capping journald disk usage ..."
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/99-jobcopilot.conf <<'EOF'
[Journal]
SystemMaxUse=500M
EOF
systemctl restart systemd-journald

echo "==> [4/6] Installing fail2ban + ufw ..."
apt-get install -y -qq fail2ban ufw

echo "==> [5/6] Firewall: allow SSH + HTTP + HTTPS only ..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "==> [6/6] Hardening SSH (key-only auth) + enabling fail2ban ..."
cat > /etc/ssh/sshd_config.d/99-jobcopilot-hardening.conf <<'EOF'
PasswordAuthentication no
PermitRootLogin prohibit-password
EOF
systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || true
systemctl enable --now fail2ban

echo "==> Provisioning complete."
