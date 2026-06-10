#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m compileall app
pytest

cd "$ROOT_DIR/frontend"
npm install
npm run build

cd "$ROOT_DIR"
bash -n deploy/install.sh
bash -n deploy/update.sh
bash -n scripts/run-backend-dev.sh
bash -n scripts/run-backend-hardware-readonly.sh
bash -n scripts/run-backend-hardware-commands.sh
bash -n scripts/run-frontend-dev.sh
bash -n scripts/run-ser2sock-simulator.sh
bash -n scripts/dev-hardware-readonly.sh
bash -n scripts/dev-hardware-commands.sh
bash -n scripts/create-hardware-admin.sh

echo "Safe test harness completed. No real hardware was contacted."
