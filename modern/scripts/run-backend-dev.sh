#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
python -m pip install -r requirements.txt

export ALARMDECODER_ADAPTER="${ALARMDECODER_ADAPTER:-fake}"
export ALARMDECODER_DATABASE_URL="${ALARMDECODER_DATABASE_URL:-sqlite:///$ROOT_DIR/backend/alarmdecoder-modern-dev.db}"
export ALARMDECODER_READ_ONLY="${ALARMDECODER_READ_ONLY:-false}"
export ALARMDECODER_ALLOW_COMMANDS="${ALARMDECODER_ALLOW_COMMANDS:-true}"

exec uvicorn app.main:app --reload --host 127.0.0.1 --port "${PORT:-8000}"
