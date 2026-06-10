#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
python -m pip install -r requirements.txt

exec python -m app.simulator \
  --host "${SIM_HOST:-127.0.0.1}" \
  --port "${SIM_PORT:-10000}" \
  --fixture "${SIM_FIXTURE:-$ROOT_DIR/backend/tests/fixtures/ser2sock-readonly-capture.txt}" \
  --capture-writes "${SIM_CAPTURE_WRITES:-$ROOT_DIR/backend/.simulator-writes.bin}"
