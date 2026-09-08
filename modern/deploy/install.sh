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

# Idempotency notice: warn if a previous install is detected.
if [[ -f "$APP_DIR/VERSION" ]]; then
  echo "NOTE: AlarmDecoder Modern version $(cat "$APP_DIR/VERSION") is already installed at $APP_DIR."
  echo "      To do a lightweight update (skipping reinstall), use deploy/update.sh instead."
  echo "      Continuing with full install anyway..."
  echo
fi

id "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin "$APP_USER"
# Add service user to dialout group for serial device access (e.g. AD2USB, AD2PI).
usermod -aG dialout "$APP_USER" 2>/dev/null || true

install -d -o "$APP_USER" -g "$APP_USER" "$DATA_DIR"
install -d -o root -g root "$CONFIG_DIR"
install -d -o root -g root "$APP_DIR"

rsync -a --delete ./ "$APP_DIR"/

# Write a VERSION file so future installs can detect the installed version.
if [[ -f "./VERSION" ]]; then
  cp "./VERSION" "$APP_DIR/VERSION"
else
  echo "1.0.0" > "$APP_DIR/VERSION"
fi

python3 -m venv "$APP_DIR/backend/.venv"
"$APP_DIR/backend/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/backend/.venv/bin/python" -m pip install -r "$APP_DIR/backend/requirements.txt"
pushd "$APP_DIR/backend" >/dev/null
"$APP_DIR/backend/.venv/bin/alembic" upgrade head
popd >/dev/null

# Frontend build: skip if a pre-built dist artifact is already present.
if [[ -d "$APP_DIR/frontend/dist" ]]; then
  echo "Using pre-built frontend assets (frontend/dist already exists — skipping npm build)."
else
  # npm (and Node.js >= 18) is required to build the frontend.
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm is required to build the production frontend." >&2
    echo "Install with: sudo apt-get install -y nodejs npm" >&2
    echo "  or for Node.js 20: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs" >&2
    exit 1
  fi
  NODE_VERSION=$(node --version 2>/dev/null | sed 's/v//' | cut -d. -f1)
  if [[ -z "$NODE_VERSION" || "$NODE_VERSION" -lt 18 ]]; then
    echo "Node.js >= 18 is required (found: $(node --version 2>/dev/null || echo 'not found'))." >&2
    echo "Install with: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs" >&2
    exit 1
  fi
  pushd "$APP_DIR/frontend" >/dev/null
  npm ci
  npm run build
  popd >/dev/null
fi

if [[ ! -f "$CONFIG_DIR/alarmdecoder-modern.env" ]]; then
  install -m 0640 -o root -g "$APP_USER" "$APP_DIR/deploy/alarmdecoder-modern.env.example" "$CONFIG_DIR/alarmdecoder-modern.env"
fi

install -m 0644 "$APP_DIR/deploy/alarmdecoder-modern.service" /etc/systemd/system/alarmdecoder-modern.service
systemctl daemon-reload
systemctl enable alarmdecoder-modern.service

echo
echo "Edit $CONFIG_DIR/alarmdecoder-modern.env, then run:"
echo "  systemctl restart alarmdecoder-modern"
echo

read -r -p 'Create admin user now? (y/N) ' reply
if [[ "$reply" =~ ^[Yy]$ ]]; then
  "$APP_DIR/backend/.venv/bin/python" -m app.cli create-admin
fi
