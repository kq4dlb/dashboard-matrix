#!/usr/bin/env bash
set -euo pipefail

SECRET_FILE="${1:-/var/lib/dashboard-matrix/secrets/icom705-password}"
RUN_USER="${DASHBOARD_MATRIX_RUN_USER:-dashboard-matrix}"
RUN_GROUP="${DASHBOARD_MATRIX_RUN_GROUP:-$RUN_USER}"

if [[ ${EUID} -ne 0 ]]; then
  echo "Run with sudo so ownership and permissions can be set safely." >&2
  exit 1
fi

read -r -s -p 'IC-705 WLAN Remote password: ' RADIO_PASSWORD
echo
if [[ -z "$RADIO_PASSWORD" ]]; then
  echo "Password cannot be empty." >&2
  exit 1
fi

install -d -m 0750 -o "$RUN_USER" -g "$RUN_GROUP" "$(dirname "$SECRET_FILE")"
printf '%s' "$RADIO_PASSWORD" > "$SECRET_FILE"
chown "$RUN_USER:$RUN_GROUP" "$SECRET_FILE"
chmod 0600 "$SECRET_FILE"
unset RADIO_PASSWORD

printf 'Password file created: %s\n' "$SECRET_FILE"
printf 'Admin secret mapping value: file:%s\n' "$SECRET_FILE"
