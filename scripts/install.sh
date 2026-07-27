#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${DASHBOARD_MATRIX_INSTALL_DIR:-/opt/dashboard-matrix}"
STATE_DIR="${DASHBOARD_MATRIX_STATE_DIR:-/var/lib/dashboard-matrix}"
SERVICE_USER="${DASHBOARD_MATRIX_USER:-dashboard-matrix}"
SOURCE_DIR="${DASHBOARD_MATRIX_SOURCE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PORT="${DASHBOARD_MATRIX_PORT:-8080}"
AUTOSTART="${DASHBOARD_MATRIX_AUTOSTART:-1}"

usage() {
  cat <<USAGE
Usage: sudo ./scripts/install.sh [options]

Options:
  --port PORT       Web port (default: 8080)
  --no-autostart    Install the service but do not enable it at boot
  --help            Show this help

Environment overrides:
  DASHBOARD_MATRIX_INSTALL_DIR
  DASHBOARD_MATRIX_STATE_DIR
  DASHBOARD_MATRIX_USER
  DASHBOARD_MATRIX_SOURCE_DIR
  DASHBOARD_MATRIX_PORT
  DASHBOARD_MATRIX_AUTOSTART=0|1
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      [[ $# -ge 2 ]] || { echo "--port requires a value" >&2; exit 2; }
      PORT="$2"
      shift 2
      ;;
    --no-autostart)
      AUTOSTART=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer with sudo." >&2
  exit 1
fi

if [[ ! "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "DASHBOARD_MATRIX_PORT must be between 1 and 65535." >&2
  exit 1
fi

if [[ "$AUTOSTART" != "0" && "$AUTOSTART" != "1" ]]; then
  echo "DASHBOARD_MATRIX_AUTOSTART must be 0 or 1." >&2
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip rsync curl

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
sed -i "s|^User=.*|User=$SERVICE_USER|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^Group=.*|Group=$SERVICE_USER|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^ExecStartPre=/usr/bin/test -x .*|ExecStartPre=/usr/bin/test -x $INSTALL_DIR/.venv/bin/python|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^ExecStartPre=/usr/bin/test -f .*|ExecStartPre=/usr/bin/test -f $INSTALL_DIR/matrix.py|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^ExecStart=.*|ExecStart=$INSTALL_DIR/.venv/bin/python $INSTALL_DIR/matrix.py|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^Environment=DASHBOARD_MATRIX_DATA_DIR=.*|Environment=DASHBOARD_MATRIX_DATA_DIR=$STATE_DIR/data|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^Environment=DASHBOARD_MATRIX_USER_PLUGINS_DIR=.*|Environment=DASHBOARD_MATRIX_USER_PLUGINS_DIR=$STATE_DIR/user_plugins|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^Environment=DASHBOARD_MATRIX_USER_SCRIPTS_DIR=.*|Environment=DASHBOARD_MATRIX_USER_SCRIPTS_DIR=$STATE_DIR/user_scripts|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^Environment=DASHBOARD_MATRIX_USER_THEMES_DIR=.*|Environment=DASHBOARD_MATRIX_USER_THEMES_DIR=$STATE_DIR/user_themes|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^Environment=DASHBOARD_MATRIX_PORT=.*|Environment=DASHBOARD_MATRIX_PORT=$PORT|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^ReadWritePaths=.*|ReadWritePaths=$STATE_DIR|" /etc/systemd/system/dashboard-matrix.service

chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR" "$STATE_DIR"
systemctl daemon-reload
if [[ "$AUTOSTART" == "1" ]]; then
  systemctl enable --now dashboard-matrix.service
  AUTOSTART_TEXT="enabled and running"
else
  systemctl disable --now dashboard-matrix.service >/dev/null 2>&1 || true
  AUTOSTART_TEXT="disabled; run sudo $INSTALL_DIR/scripts/manage-autostart.sh enable when ready"
fi

HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
HOST_IP="${HOST_IP:-127.0.0.1}"
printf '\nDashboard Matrix installed at %s\n' "$INSTALL_DIR"
printf 'Autostart: %s\n' "$AUTOSTART_TEXT"
printf 'Dashboard URL: http://%s:%s/\n' "$HOST_IP" "$PORT"
printf 'Complete the first-run wizard in your browser.\n'
