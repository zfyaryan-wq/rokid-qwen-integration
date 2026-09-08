#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"

if [[ "$ROOT_DIR" != "/opt/omni" ]]; then
  echo "Clone or copy the repository to /opt/omni before running this script." >&2
  exit 1
fi

if [[ ! -f "$DEPLOY_DIR/.env" ]]; then
  echo "Create deploy/.env from deploy/.env.example first." >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 nginx wireguard curl
sudo systemctl enable --now docker

sudo mkdir -p /srv/omni/releases
sudo chown -R "$USER":"$USER" /srv/omni/releases
chmod 600 "$DEPLOY_DIR/.env"

sudo install -m 0644 "$DEPLOY_DIR/nginx/omni.conf" /etc/nginx/sites-available/omni
sudo ln -sfn /etc/nginx/sites-available/omni /etc/nginx/sites-enabled/omni
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx

sudo install -m 0644 "$DEPLOY_DIR/systemd/omni.service" /etc/systemd/system/omni.service
sudo systemctl daemon-reload
sudo systemctl enable --now omni

curl --fail --silent --show-error http://127.0.0.1/health
echo
echo "Omni backend is running. Configure WireGuard before testing from Android."
