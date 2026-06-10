#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/alarmdecoder-modern
APP_USER=alarmdecoder-modern

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root on Raspberry Pi OS." >&2
  exit 1
fi

systemctl stop alarmdecoder-modern.service || true
rsync -a --delete ./ "$APP_DIR"/
"$APP_DIR/backend/.venv/bin/python" -m pip install -r "$APP_DIR/backend/requirements.txt"
pushd "$APP_DIR/backend" >/dev/null
"$APP_DIR/backend/.venv/bin/alembic" upgrade head
popd >/dev/null
pushd "$APP_DIR/frontend" >/dev/null
npm ci
npm run build
popd >/dev/null
chown -R root:root "$APP_DIR"
chown -R "$APP_USER:$APP_USER" /var/lib/alarmdecoder-modern
systemctl start alarmdecoder-modern.service
systemctl status --no-pager alarmdecoder-modern.service
