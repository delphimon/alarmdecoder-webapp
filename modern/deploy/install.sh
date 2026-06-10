#!/usr/bin/env bash
set -euo pipefail

APP_USER=alarmdecoder-modern
APP_DIR=/opt/alarmdecoder-modern
DATA_DIR=/var/lib/alarmdecoder-modern
CONFIG_DIR=/etc/alarmdecoder-modern

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root on Raspberry Pi OS." >&2
  exit 1
fi

id "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin "$APP_USER"
install -d -o "$APP_USER" -g "$APP_USER" "$DATA_DIR"
install -d -o root -g root "$CONFIG_DIR"
install -d -o root -g root "$APP_DIR"

rsync -a --delete ./ "$APP_DIR"/

python3 -m venv "$APP_DIR/backend/.venv"
"$APP_DIR/backend/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/backend/.venv/bin/python" -m pip install -r "$APP_DIR/backend/requirements.txt"
pushd "$APP_DIR/backend" >/dev/null
"$APP_DIR/backend/.venv/bin/alembic" upgrade head
popd >/dev/null

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to build the production frontend." >&2
  exit 1
fi

pushd "$APP_DIR/frontend" >/dev/null
npm ci
npm run build
popd >/dev/null

if [[ ! -f "$CONFIG_DIR/alarmdecoder-modern.env" ]]; then
  install -m 0640 -o root -g "$APP_USER" "$APP_DIR/deploy/alarmdecoder-modern.env.example" "$CONFIG_DIR/alarmdecoder-modern.env"
fi

install -m 0644 "$APP_DIR/deploy/alarmdecoder-modern.service" /etc/systemd/system/alarmdecoder-modern.service
systemctl daemon-reload
systemctl enable alarmdecoder-modern.service

echo "Edit $CONFIG_DIR/alarmdecoder-modern.env, create an admin user, then run:"
echo "  systemctl restart alarmdecoder-modern"
