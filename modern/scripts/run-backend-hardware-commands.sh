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
export ALARMDECODER_READ_ONLY=false
export ALARMDECODER_ALLOW_COMMANDS=true
export ALARMDECODER_AUTH_REQUIRED=true
export ALARMDECODER_DATABASE_URL="${ALARMDECODER_DATABASE_URL:-sqlite:///$ROOT_DIR/backend/alarmdecoder-modern-hardware-dev.db}"

echo "Starting backend in COMMAND-ENABLED hardware mode."
echo "Adapter: $ALARMDECODER_ADAPTER"
echo "Target: ${ALARMDECODER_SER2SOCK_HOST}:${ALARMDECODER_SER2SOCK_PORT}"
echo "READ_ONLY=false, ALLOW_COMMANDS=true, AUTH_REQUIRED=true"
echo "Commands can be sent to the alarm panel after you sign in as operator/admin."

exec uvicorn app.main:app --reload --host 127.0.0.1 --port "${PORT:-8000}"
