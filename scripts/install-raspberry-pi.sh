#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${DASHBOARD_MATRIX_INSTALL_DIR:-/opt/dashboard-matrix}"
DATA_DIR="${DASHBOARD_MATRIX_DATA_DIR:-/var/lib/dashboard-matrix}"
SERVICE_USER="${DASHBOARD_MATRIX_USER:-dashboard-matrix}"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer with sudo." >&2
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip git rsync chromium-browser || \
  apt-get install -y python3 python3-venv python3-pip git chromium

id "$SERVICE_USER" >/dev/null 2>&1 || useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
mkdir -p "$INSTALL_DIR" "$DATA_DIR"/{data,user_plugins,user_scripts,user_themes}
rsync -a --delete --exclude '.git' --exclude '.venv' "$SOURCE_DIR/" "$INSTALL_DIR/"
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR" "$DATA_DIR"

if [[ ! -f /etc/dashboard-matrix.env ]]; then
  SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  printf 'DASHBOARD_MATRIX_SESSION_SECRET=%s\n' "$SESSION_SECRET" >/etc/dashboard-matrix.env
  chmod 600 /etc/dashboard-matrix.env
fi

cat >/etc/systemd/system/dashboard-matrix.service <<SERVICE
[Unit]
Description=KQ4DLB Dashboard Matrix
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
Environment=DASHBOARD_MATRIX_DATA_DIR=$DATA_DIR/data
Environment=DASHBOARD_MATRIX_USER_PLUGINS_DIR=$DATA_DIR/user_plugins
Environment=DASHBOARD_MATRIX_USER_SCRIPTS_DIR=$DATA_DIR/user_scripts
Environment=DASHBOARD_MATRIX_USER_THEMES_DIR=$DATA_DIR/user_themes
Environment=DASHBOARD_MATRIX_HOST=0.0.0.0
Environment=DASHBOARD_MATRIX_PORT=8080
EnvironmentFile=-/etc/dashboard-matrix.env
ExecStart=$INSTALL_DIR/.venv/bin/python $INSTALL_DIR/matrix.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$DATA_DIR

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable --now dashboard-matrix.service
printf '\nDashboard Matrix is running at http://%s:8080/\n' "$(hostname -I | awk '{print $1}')"
