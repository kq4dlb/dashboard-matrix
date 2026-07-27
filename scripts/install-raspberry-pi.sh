#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${DASHBOARD_MATRIX_INSTALL_DIR:-/opt/dashboard-matrix}"
DATA_DIR="${DASHBOARD_MATRIX_DATA_DIR:-/var/lib/dashboard-matrix}"
SERVICE_USER="${DASHBOARD_MATRIX_USER:-dashboard-matrix}"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${DASHBOARD_MATRIX_PORT:-8080}"
AUTOSTART="${DASHBOARD_MATRIX_AUTOSTART:-1}"
KIOSK_USER="${DASHBOARD_MATRIX_KIOSK_USER:-}"

usage() {
  cat <<USAGE
Usage: sudo ./scripts/install-raspberry-pi.sh [options]

Options:
  --port PORT         Web port (default: 8080)
  --no-autostart      Install without enabling the server at boot
  --kiosk-user USER   Open the dashboard in Chromium when USER signs in
  --help              Show this help
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
    --kiosk-user)
      [[ $# -ge 2 ]] || { echo "--kiosk-user requires a username" >&2; exit 2; }
      KIOSK_USER="$2"
      shift 2
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
  echo "Port must be between 1 and 65535." >&2
  exit 1
fi
if [[ "$AUTOSTART" != "0" && "$AUTOSTART" != "1" ]]; then
  echo "DASHBOARD_MATRIX_AUTOSTART must be 0 or 1." >&2
  exit 1
fi
if [[ -n "$KIOSK_USER" ]] && ! id "$KIOSK_USER" >/dev/null 2>&1; then
  echo "Kiosk user '$KIOSK_USER' does not exist." >&2
  exit 1
fi

apt-get update
BASE_PACKAGES=(python3 python3-venv python3-pip git rsync curl)
if [[ -n "$KIOSK_USER" ]]; then
  if apt-cache show chromium >/dev/null 2>&1; then
    BASE_PACKAGES+=(chromium)
  else
    BASE_PACKAGES+=(chromium-browser)
  fi
fi
apt-get install -y "${BASE_PACKAGES[@]}"

id "$SERVICE_USER" >/dev/null 2>&1 || useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
mkdir -p "$INSTALL_DIR" "$DATA_DIR"/{data,user_plugins,user_scripts,user_themes,logs}
rsync -a --delete --exclude '.git' --exclude '.venv' --exclude '.pytest_cache' --exclude '__pycache__' "$SOURCE_DIR/" "$INSTALL_DIR/"
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR" "$DATA_DIR"

if [[ ! -f /etc/dashboard-matrix.env ]]; then
  SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  printf 'DASHBOARD_MATRIX_SESSION_SECRET=%s\n' "$SESSION_SECRET" >/etc/dashboard-matrix.env
  chmod 600 /etc/dashboard-matrix.env
fi

install -m 0644 "$INSTALL_DIR/systemd/dashboard-matrix.service" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^User=.*|User=$SERVICE_USER|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^Group=.*|Group=$SERVICE_USER|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^ExecStartPre=/usr/bin/test -x .*|ExecStartPre=/usr/bin/test -x $INSTALL_DIR/.venv/bin/python|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^ExecStartPre=/usr/bin/test -f .*|ExecStartPre=/usr/bin/test -f $INSTALL_DIR/matrix.py|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^ExecStart=.*|ExecStart=$INSTALL_DIR/.venv/bin/python $INSTALL_DIR/matrix.py|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^Environment=DASHBOARD_MATRIX_DATA_DIR=.*|Environment=DASHBOARD_MATRIX_DATA_DIR=$DATA_DIR/data|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^Environment=DASHBOARD_MATRIX_USER_PLUGINS_DIR=.*|Environment=DASHBOARD_MATRIX_USER_PLUGINS_DIR=$DATA_DIR/user_plugins|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^Environment=DASHBOARD_MATRIX_USER_SCRIPTS_DIR=.*|Environment=DASHBOARD_MATRIX_USER_SCRIPTS_DIR=$DATA_DIR/user_scripts|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^Environment=DASHBOARD_MATRIX_USER_THEMES_DIR=.*|Environment=DASHBOARD_MATRIX_USER_THEMES_DIR=$DATA_DIR/user_themes|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^Environment=DASHBOARD_MATRIX_PORT=.*|Environment=DASHBOARD_MATRIX_PORT=$PORT|" /etc/systemd/system/dashboard-matrix.service
sed -i "s|^ReadWritePaths=.*|ReadWritePaths=$DATA_DIR|" /etc/systemd/system/dashboard-matrix.service

systemctl daemon-reload
if [[ "$AUTOSTART" == "1" ]]; then
  systemctl enable --now dashboard-matrix.service
  AUTOSTART_TEXT="enabled and running"
else
  systemctl disable --now dashboard-matrix.service >/dev/null 2>&1 || true
  AUTOSTART_TEXT="disabled"
fi

if [[ -n "$KIOSK_USER" ]]; then
  KIOSK_HOME="$(getent passwd "$KIOSK_USER" | cut -d: -f6)"
  KIOSK_GROUP="$(id -gn "$KIOSK_USER")"
  AUTOSTART_DIR="$KIOSK_HOME/.config/autostart"
  install -d -m 0755 -o "$KIOSK_USER" -g "$KIOSK_GROUP" "$AUTOSTART_DIR"
  cat >"$AUTOSTART_DIR/dashboard-matrix-kiosk.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Dashboard Matrix Kiosk
Comment=Open Dashboard Matrix after desktop login
Exec=env DASHBOARD_MATRIX_PORT=$PORT $INSTALL_DIR/scripts/kiosk.sh
Terminal=false
X-GNOME-Autostart-enabled=true
DESKTOP
  chown "$KIOSK_USER:$KIOSK_GROUP" "$AUTOSTART_DIR/dashboard-matrix-kiosk.desktop"
  KIOSK_TEXT="enabled for desktop user $KIOSK_USER"
else
  KIOSK_TEXT="not configured"
fi

HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
HOST_IP="${HOST_IP:-127.0.0.1}"
printf '\nDashboard Matrix URL: http://%s:%s/\n' "$HOST_IP" "$PORT"
printf 'Server autostart: %s\n' "$AUTOSTART_TEXT"
printf 'Kiosk autostart: %s\n' "$KIOSK_TEXT"
