#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
python -m pip install -r requirements.txt

export ALARMDECODER_ADAPTER="${ALARMDECODER_ADAPTER:-ser2sock}"
export ALARMDECODER_SER2SOCK_HOST="${ALARMDECODER_SER2SOCK_HOST:-alarmdecoder.local}"
export ALARMDECODER_SER2SOCK_PORT="${ALARMDECODER_SER2SOCK_PORT:-10000}"
export ALARMDECODER_SER2SOCK_TLS="${ALARMDECODER_SER2SOCK_TLS:-false}"
export ALARMDECODER_READ_ONLY=true
export ALARMDECODER_ALLOW_COMMANDS=false
export ALARMDECODER_AUTH_REQUIRED="${ALARMDECODER_AUTH_REQUIRED:-false}"
export ALARMDECODER_DATABASE_URL="${ALARMDECODER_DATABASE_URL:-sqlite:///$ROOT_DIR/backend/alarmdecoder-modern-hardware-dev.db}"

echo "Starting backend in read-only hardware mode."
echo "Adapter: $ALARMDECODER_ADAPTER"
echo "Target: ${ALARMDECODER_SER2SOCK_HOST}:${ALARMDECODER_SER2SOCK_PORT}"
echo "READ_ONLY=true, ALLOW_COMMANDS=false"

exec uvicorn app.main:app --reload --host 127.0.0.1 --port "${PORT:-8000}"
