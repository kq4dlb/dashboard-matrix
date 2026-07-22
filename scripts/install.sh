#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${DASHBOARD_MATRIX_INSTALL_DIR:-/opt/dashboard-matrix}"
STATE_DIR="${DASHBOARD_MATRIX_STATE_DIR:-/var/lib/dashboard-matrix}"
SERVICE_USER="${DASHBOARD_MATRIX_USER:-dashboard-matrix}"
SOURCE_DIR="${DASHBOARD_MATRIX_SOURCE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PORT="${DASHBOARD_MATRIX_PORT:-8080}"

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer with sudo." >&2
  exit 1
fi

if [[ ! "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "DASHBOARD_MATRIX_PORT must be between 1 and 65535." >&2
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip rsync

id "$SERVICE_USER" >/dev/null 2>&1 || \
  useradd --system --home "$STATE_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"

mkdir -p "$INSTALL_DIR" "$STATE_DIR"/{data,user_plugins,user_scripts,user_themes,logs}
rsync -a --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '.pytest_cache' \
  --exclude '__pycache__' \
  --exclude 'build' \
  --exclude 'dist' \
  "$SOURCE_DIR/" "$INSTALL_DIR/"

python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

if [[ ! -f /etc/dashboard-matrix.env ]]; then
  SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  cat >/etc/dashboard-matrix.env <<ENV
DASHBOARD_MATRIX_SESSION_SECRET=$SESSION_SECRET
ENV
  chmod 600 /etc/dashboard-matrix.env
fi

install -m 0644 "$INSTALL_DIR/systemd/dashboard-matrix.service" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^Environment=DASHBOARD_MATRIX_PORT=.*|Environment=DASHBOARD_MATRIX_PORT=$PORT|" /etc/systemd/system/dashboard-matrix.service

chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR" "$STATE_DIR"
systemctl daemon-reload
systemctl enable --now dashboard-matrix.service

HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
HOST_IP="${HOST_IP:-127.0.0.1}"
printf '\nDashboard Matrix is running at http://%s:%s/\n' "$HOST_IP" "$PORT"
printf 'Complete the first-run wizard in your browser.\n'
