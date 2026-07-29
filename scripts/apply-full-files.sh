#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${1:-/opt/dashboard-matrix}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${TARGET_DIR%/}/backups/icom705-full-sync-${STAMP}"

if [[ ! -f "$TARGET_DIR/matrix.py" || ! -d "$TARGET_DIR/app" ]]; then
  echo "Dashboard Matrix was not found at: $TARGET_DIR" >&2
  echo "Usage: $0 /path/to/dashboard-matrix" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR/app" "$BACKUP_DIR/plugins/icom-705-ip"
for file in \
  app/main.py \
  app/plugin_manager.py \
  app/plugin_worker.py \
  plugins/icom-705-ip/manifest.json \
  plugins/icom-705-ip/plugin.py \
  plugins/icom-705-ip/README.md \
  requirements-optional.txt; do
  if [[ -f "$TARGET_DIR/$file" ]]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$file")"
    cp -a "$TARGET_DIR/$file" "$BACKUP_DIR/$file"
  fi
done

install -D -m 0644 "$BUNDLE_DIR/app/main.py" "$TARGET_DIR/app/main.py"
install -D -m 0644 "$BUNDLE_DIR/app/plugin_manager.py" "$TARGET_DIR/app/plugin_manager.py"
install -D -m 0644 "$BUNDLE_DIR/app/plugin_worker.py" "$TARGET_DIR/app/plugin_worker.py"
install -D -m 0644 "$BUNDLE_DIR/plugins/icom-705-ip/manifest.json" "$TARGET_DIR/plugins/icom-705-ip/manifest.json"
install -D -m 0644 "$BUNDLE_DIR/plugins/icom-705-ip/plugin.py" "$TARGET_DIR/plugins/icom-705-ip/plugin.py"
install -D -m 0644 "$BUNDLE_DIR/plugins/icom-705-ip/README.md" "$TARGET_DIR/plugins/icom-705-ip/README.md"
install -D -m 0644 "$BUNDLE_DIR/requirements-optional.txt" "$TARGET_DIR/requirements-optional.txt"

PYTHON_BIN="$TARGET_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

"$PYTHON_BIN" -m compileall -q \
  "$TARGET_DIR/app/main.py" \
  "$TARGET_DIR/app/plugin_manager.py" \
  "$TARGET_DIR/app/plugin_worker.py" \
  "$TARGET_DIR/plugins/icom-705-ip/plugin.py"

printf 'Full files installed.\nBackup: %s\n' "$BACKUP_DIR"
printf 'Restart the exact process that serves Dashboard Matrix.\n'
