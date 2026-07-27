#!/usr/bin/env bash
set -euo pipefail

PORT="${DASHBOARD_MATRIX_PORT:-8080}"
URL="${DASHBOARD_MATRIX_KIOSK_URL:-http://127.0.0.1:${PORT}/dashboard}"
HEALTH_URL="${DASHBOARD_MATRIX_HEALTH_URL:-http://127.0.0.1:${PORT}/health}"

find_browser() {
  if [[ -n "${DASHBOARD_MATRIX_KIOSK_BROWSER:-}" ]]; then
    command -v "$DASHBOARD_MATRIX_KIOSK_BROWSER" || return 1
    return
  fi
  command -v chromium-browser 2>/dev/null || \
    command -v chromium 2>/dev/null || \
    command -v google-chrome 2>/dev/null || \
    command -v google-chrome-stable 2>/dev/null
}

BROWSER="$(find_browser)" || {
  echo "No Chromium-compatible browser was found." >&2
  exit 1
}

until curl -fsS --max-time 3 "$HEALTH_URL" >/dev/null; do
  sleep 2
done

exec "$BROWSER" \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --check-for-update-interval=31536000 \
  "$URL"
