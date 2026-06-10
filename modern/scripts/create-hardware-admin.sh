#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
python -m pip install -r requirements.txt

export ALARMDECODER_DATABASE_URL="${ALARMDECODER_DATABASE_URL:-sqlite:///$ROOT_DIR/backend/alarmdecoder-modern-hardware-dev.db}"

exec python -m app.cli create-admin --username "${1:-admin}"
