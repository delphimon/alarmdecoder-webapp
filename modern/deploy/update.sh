#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/alarmdecoder-modern
APP_USER=alarmdecoder-modern

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root on Raspberry Pi OS." >&2
  exit 1
fi

echo "Stopping service (brief downtime expected)..."
systemctl stop alarmdecoder-modern.service || true

rsync -a --delete ./ "$APP_DIR"/
"$APP_DIR/backend/.venv/bin/python" -m pip install -r "$APP_DIR/backend/requirements.txt"
pushd "$APP_DIR/backend" >/dev/null
"$APP_DIR/backend/.venv/bin/alembic" upgrade head
popd >/dev/null

# Frontend build: skip if a pre-built dist artifact is already present.
if [[ -d "$APP_DIR/frontend/dist" ]]; then
  echo "Using pre-built frontend assets (frontend/dist already exists — skipping npm build)."
else
  pushd "$APP_DIR/frontend" >/dev/null
  npm ci
  npm run build
  popd >/dev/null
fi

chown -R root:root "$APP_DIR"
chown -R "$APP_USER:$APP_USER" /var/lib/alarmdecoder-modern
systemctl start alarmdecoder-modern.service
systemctl status --no-pager alarmdecoder-modern.service

# Health check: poll /health up to 15 times with 2s between attempts.
echo -n "Waiting for service to become healthy"
HEALTHY=false
for i in $(seq 1 15); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    HEALTHY=true
    break
  fi
  echo -n "."
  sleep 2
done
echo

if [[ "$HEALTHY" == "true" ]]; then
  echo "Service is healthy."
else
  echo "WARNING: service may not be healthy — check: journalctl -u alarmdecoder-modern" >&2
  exit 1
fi
