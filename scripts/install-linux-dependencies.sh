#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-/opt/dashboard-matrix}"
VENV_PIP="$TARGET_DIR/.venv/bin/pip"
VENV_PYTHON="$TARGET_DIR/.venv/bin/python"

if [[ ! -x "$VENV_PIP" || ! -x "$VENV_PYTHON" ]]; then
  echo "Dashboard Matrix virtual environment was not found at $TARGET_DIR/.venv" >&2
  exit 1
fi

if [[ ${EUID} -eq 0 ]]; then
  apt-get update
  apt-get install -y libopus0 libportaudio2
else
  sudo apt-get update
  sudo apt-get install -y libopus0 libportaudio2
fi

"$VENV_PIP" install 'rigplane>=2.11,<3.0'
"$VENV_PYTHON" -c 'import rigplane, sys; print("RigPlane ready on Python", sys.version.split()[0])'
