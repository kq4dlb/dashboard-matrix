#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${DASHBOARD_MATRIX_SERVICE_NAME:-dashboard-matrix.service}"
ACTION="${1:-status}"

usage() {
  cat <<USAGE
Usage: sudo ./scripts/manage-autostart.sh <command>

Commands:
  enable    Enable Dashboard Matrix at boot and start it now
  disable   Stop Dashboard Matrix and disable boot startup
  start     Start Dashboard Matrix now
  stop      Stop Dashboard Matrix now
  restart   Restart Dashboard Matrix now
  status    Show enabled and running state
  logs      Follow service logs

The Linux/Raspberry Pi installer enables autostart by default. Set
DASHBOARD_MATRIX_SERVICE_NAME to manage a differently named unit.
USAGE
}

require_systemd() {
  command -v systemctl >/dev/null 2>&1 || {
    echo "systemctl was not found. This command requires a systemd-based Linux system." >&2
    exit 1
  }
}

require_root() {
  if [[ ${EUID} -ne 0 ]]; then
    echo "Run this command with sudo." >&2
    exit 1
  fi
}

print_status() {
  local enabled="unknown"
  local active="unknown"
  enabled="$(systemctl is-enabled "$SERVICE_NAME" 2>/dev/null || true)"
  active="$(systemctl is-active "$SERVICE_NAME" 2>/dev/null || true)"
  printf 'Service: %s\nAutostart: %s\nRunning: %s\n' "$SERVICE_NAME" "$enabled" "$active"
  systemctl status "$SERVICE_NAME" --no-pager --lines=8 || true
}

require_systemd
case "$ACTION" in
  enable)
    require_root
    systemctl daemon-reload
    systemctl enable --now "$SERVICE_NAME"
    print_status
    ;;
  disable)
    require_root
    systemctl disable --now "$SERVICE_NAME"
    print_status
    ;;
  start|stop|restart)
    require_root
    systemctl "$ACTION" "$SERVICE_NAME"
    print_status
    ;;
  status)
    print_status
    ;;
  logs)
    journalctl -u "$SERVICE_NAME" -f --no-pager
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
