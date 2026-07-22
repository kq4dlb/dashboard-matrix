#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GEN_HOME="${RPI_IMAGE_GEN_HOME:-$HOME/rpi-image-gen}"
CONFIG="${RPI_IMAGE_CONFIG:-$GEN_HOME/config/trixie-minbase.yaml}"
OUTPUT_DIR="${DASHBOARD_MATRIX_IMAGE_OUTPUT:-$ROOT/dist/raspberry-pi}"

command -v git >/dev/null
command -v virt-customize >/dev/null || {
  echo "virt-customize is required (Debian package: libguestfs-tools)." >&2
  exit 1
}

if [[ ! -x "$GEN_HOME/rpi-image-gen" ]]; then
  git clone --depth 1 https://github.com/raspberrypi/rpi-image-gen.git "$GEN_HOME"
  if [[ "${RPI_IMAGE_GEN_INSTALL_DEPS:-0}" == "1" ]]; then
    (cd "$GEN_HOME" && sudo ./install_deps.sh)
  else
    echo "Run $GEN_HOME/install_deps.sh once, or set RPI_IMAGE_GEN_INSTALL_DEPS=1." >&2
    exit 1
  fi
fi

mkdir -p "$OUTPUT_DIR"
(cd "$GEN_HOME" && ./rpi-image-gen build -c "$CONFIG")
IMAGE="$(find "$GEN_HOME/work" -type f -name '*.img' -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)"
[[ -n "$IMAGE" ]] || { echo "No generated image was found." >&2; exit 1; }

BUNDLE="$(mktemp --suffix=.tar.gz)"
trap 'rm -f "$BUNDLE"' EXIT
tar --exclude=.git --exclude=.venv --exclude=dist -C "$ROOT" -czf "$BUNDLE" .

virt-customize -a "$IMAGE" --network \
  --install python3,python3-venv,python3-pip,avahi-daemon,ca-certificates \
  --mkdir /opt/dashboard-matrix \
  --mkdir /var/lib/dashboard-matrix/data \
  --mkdir /var/lib/dashboard-matrix/user_plugins \
  --mkdir /var/lib/dashboard-matrix/user_scripts \
  --mkdir /var/lib/dashboard-matrix/user_themes \
  --upload "$BUNDLE:/tmp/dashboard-matrix.tar.gz" \
  --run-command 'tar -xzf /tmp/dashboard-matrix.tar.gz -C /opt/dashboard-matrix' \
  --run-command 'python3 -m venv /opt/dashboard-matrix/.venv' \
  --run-command '/opt/dashboard-matrix/.venv/bin/pip install --upgrade pip' \
  --run-command '/opt/dashboard-matrix/.venv/bin/pip install -r /opt/dashboard-matrix/requirements.txt' \
  --run-command 'id dashboard-matrix >/dev/null 2>&1 || useradd --system --home /var/lib/dashboard-matrix --shell /usr/sbin/nologin dashboard-matrix' \
  --run-command 'chown -R dashboard-matrix:dashboard-matrix /opt/dashboard-matrix /var/lib/dashboard-matrix' \
  --copy-in "$ROOT/systemd/dashboard-matrix.service:/etc/systemd/system" \
  --run-command "python3 -c 'import secrets; print(\"DASHBOARD_MATRIX_SESSION_SECRET=\"+secrets.token_urlsafe(48))' >/etc/dashboard-matrix.env" \
  --run-command 'chmod 600 /etc/dashboard-matrix.env' \
  --run-command 'systemctl enable dashboard-matrix.service avahi-daemon.service' \
  --run-command 'rm -f /tmp/dashboard-matrix.tar.gz'

TARGET="$OUTPUT_DIR/dashboard-matrix-0.1.0-beta-rpi-arm64.img"
cp "$IMAGE" "$TARGET"
xz -T0 -f "$TARGET"
sha256sum "$TARGET.xz" >"$TARGET.xz.sha256"
echo "Created $TARGET.xz"
