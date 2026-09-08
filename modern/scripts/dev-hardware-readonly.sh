#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

PORT="$BACKEND_PORT" "$ROOT_DIR/scripts/run-backend-hardware-readonly.sh" &
BACKEND_PID=$!

echo "Waiting for backend health on 127.0.0.1:${BACKEND_PORT}..."
HEALTHY=0
for _ in {1..60}; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "ERROR: Backend process exited prematurely. Check logs above." >&2
    exit 1
  fi
  if curl -fsS "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null 2>&1; then
    HEALTHY=1
    break
  fi
  sleep 0.5
done

if [[ "$HEALTHY" -ne 1 ]]; then
  echo "ERROR: Backend failed to respond on http://127.0.0.1:${BACKEND_PORT}/health within 30 seconds." >&2
  exit 1
fi

cd "$ROOT_DIR/frontend"
npm install
export VITE_BACKEND_ORIGIN="http://127.0.0.1:${BACKEND_PORT}"
exec npm run dev -- --host "$FRONTEND_HOST"
