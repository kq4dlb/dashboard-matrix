#!/usr/bin/env bash
set -euo pipefail
until curl -fsS http://127.0.0.1:8080/health >/dev/null; do sleep 2; done
chromium --kiosk --noerrdialogs --disable-infobars --check-for-update-interval=31536000 http://127.0.0.1:8080/dashboard
