# AlarmDecoder Modern

Modern replacement AlarmDecoder web app. This implementation is separate from the legacy Python 2 app and does not import or depend on legacy code.

## Included

- **FastAPI backend**: Modern async Python (3.12+) application with SQLAlchemy 2.0 and Pydantic v2.
- **React + TypeScript + Vite frontend**: Accessible, modern UI with dark mode (OS auto / light / dark), phosphor-green LCD, and native `<dialog>` modals.
- **Progressive Web App (PWA)**: Installable on mobile and desktop, home-screen icon, web manifest, and caching service worker.
- **WebAuthn Passkeys**: Fast, secure passwordless login using Touch ID, Face ID, Windows Hello, or hardware security keys (FIDO2/WebAuthn).
- **AlarmDecoder Protocol Bitfield Parser**: Full 20-bit status field parser extracting ready, armed away/stay, chime, fire, low battery, check zones, AC power, and beep counts directly from raw frames with LCD text fallback.
- **Server-Side PIN Synthesis**: High-level commands (`arm_away`, `arm_stay`, `disarm`, `chime_toggle`) translated automatically to panel-specific sequences for Honeywell/ADEMCO Vista and DSC panels.
- **Encrypted PIN Storage**: Panel PIN is encrypted at rest using HKDF-SHA256 derived keys and Fernet symmetric encryption; never returned to the client or logged.
- **Reliable Persistence**: SQLite WAL (Write-Ahead Logging) mode with event persistence decoupled from the async event loop to eliminate WebSocket broadcast latency.
- **Hardware Device Adapters**:
  - `ser2sock`: TCP network adapter for network-attached AlarmDecoder devices (e.g., Raspberry Pi running ser2sock).
  - `serial`: Direct serial adapter for AD2USB, AD2PI, and AD2SERIAL devices (with automatic `dialout` group management).
  - `fake`: In-memory simulated adapter for offline development and CI.
- **Keypad UI**: ADEMCO and DSC layouts, LCD emulator with custom cursor, beep audio playback with mute control, quick action buttons, and dangerous action confirmations.
- **Authentication & Security**:
  - Viewer, Operator, and Admin role hierarchy.
  - HttpOnly SameSite=Strict cookie sessions with double-submit CSRF protection.
  - Revocable SHA-256 hashed API bearer tokens.
  - Comprehensive redaction of alarm codes, credentials, and notification secrets from logs, audits, and events.
- **Notifications**: Async Webhook and SMTP email notification providers.
- **Dev & Test Tooling**:
  - Automated local development scripts with fail-fast health monitoring.
  - Local ser2sock simulator and comprehensive test harness (43 automated tests).
  - Automated GitHub Actions release workflow building deployable tarballs.
  - Production-ready systemd, environment, and installation scripts for Raspberry Pi OS.

## Backend

From this directory:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Useful endpoints:

- `GET http://localhost:8000/health`
- `GET http://localhost:8000/ready`
- `GET http://localhost:8000/api/state`
- `GET http://localhost:8000/api/events`
- `GET http://localhost:8000/api/snapshot`
- `GET http://localhost:8000/api/diagnostics/connection`
- `GET http://localhost:8000/api/diagnostics/raw-messages`
- `GET http://localhost:8000/api/diagnostics/events`
- `GET http://localhost:8000/api/config/effective`
- `GET http://localhost:8000/api/history/events`
- `GET http://localhost:8000/api/history/raw-messages`
- `GET/PUT http://localhost:8000/api/settings` (persists settings in DB and hot-reloads hardware connection)
- `GET/POST http://localhost:8000/api/settings/pin` (Panel PIN configuration - write-only / masked)
- `GET/PUT http://localhost:8000/api/zones`
- `DELETE http://localhost:8000/api/zones/{zone_id}`
- `GET/POST/PATCH/DELETE http://localhost:8000/api/admin/users`
- `GET/PUT http://localhost:8000/api/admin/notifications`
- `GET http://localhost:8000/api/audit`
- `GET http://localhost:8000/api/auth/me`
- `POST http://localhost:8000/api/auth/login`
- `POST http://localhost:8000/api/auth/logout`
- `GET http://localhost:8000/api/auth/passkey/register/start`
- `POST http://localhost:8000/api/auth/passkey/register/finish`
- `GET http://localhost:8000/api/auth/passkey/login/start`
- `POST http://localhost:8000/api/auth/passkey/login/finish`
- `GET/DELETE http://localhost:8000/api/auth/passkey/credentials`
- `POST http://localhost:8000/api/keypad/command`
- `WS ws://localhost:8000/ws/state`

Example command with server-side PIN synthesis (preferred):

```bash
curl -X POST http://localhost:8000/api/keypad/command \
  -H 'Content-Type: application/json' \
  -H 'X-CSRF-Token: <token>' \
  -d '{"command":"arm_away"}'
```

Example raw keystroke command (admin only):

```bash
curl -X POST http://localhost:8000/api/keypad/command \
  -H 'Content-Type: application/json' \
  -H 'X-CSRF-Token: <token>' \
  -d '{"keys":"AWAY","dangerous_confirmed":true}'
```

Submitted keypad values and PINs are treated as sensitive. The backend redacts command values in events, audit logs, diagnostics, and notifications.

When using browser cookie auth, mutating requests must send the CSRF token from `/api/auth/me` or `/api/auth/login` in the `X-CSRF-Token` header.

## Local Mac Development

Use three terminals for a full local run:

```bash
./scripts/run-backend-dev.sh
./scripts/run-frontend-dev.sh
```

Open `http://localhost:5173`.

For read-only development against your actual ser2sock hardware, use:

```bash
./scripts/dev-hardware-readonly.sh
```

That command starts the backend against `alarmdecoder.local:10000` and the frontend against the local backend. It forces:

- `ALARMDECODER_READ_ONLY=true`
- `ALARMDECODER_ALLOW_COMMANDS=false`

So keypad commands remain blocked while you validate live state and diagnostics.

For command-enabled development against your actual ser2sock hardware:

```bash
./scripts/create-hardware-admin.sh admin
./scripts/dev-hardware-commands.sh
```

If your AlarmDecoder device is on a specific IP or custom port:

```bash
ALARMDECODER_SER2SOCK_HOST=192.168.1.50 ALARMDECODER_SER2SOCK_PORT=10000 ./scripts/dev-hardware-commands.sh
```

Then open `http://127.0.0.1:5173`, sign in as `admin`, and:
1. Go to **Settings** > **Panel PIN** to configure your panel's 4-digit PIN (stored with HKDF-SHA256 + Fernet encryption). This enables high-level one-touch **Arm Away**, **Arm Stay**, and **Disarm** buttons.
2. Go to **Settings** > **Security & Passkeys** to enroll your device's biometric authenticator (Touch ID, Face ID, Windows Hello, or security key) for 1-click passwordless login.

This mode forces:

- `ALARMDECODER_READ_ONLY=false`
- `ALARMDECODER_ALLOW_COMMANDS=true`
- `ALARMDECODER_AUTH_REQUIRED=true`

Only signed-in `operator` or `admin` users can send commands. The app still redacts submitted keypad values and PINs from events, diagnostics, audit logs, and notifications.

To exercise the real network adapter path without hardware, start the local ser2sock simulator in a third terminal and run the backend in read-only ser2sock mode:

```bash
./scripts/run-ser2sock-simulator.sh

ALARMDECODER_ADAPTER=ser2sock \
ALARMDECODER_SER2SOCK_HOST=127.0.0.1 \
ALARMDECODER_SER2SOCK_PORT=10000 \
ALARMDECODER_READ_ONLY=true \
ALARMDECODER_ALLOW_COMMANDS=false \
./scripts/run-backend-dev.sh
```

The simulator writes any bytes received from the app to `backend/.simulator-writes.bin`. In read-only validation that file should remain empty. This simulator is local-only and never connects to `alarmdecoder.local`.

## Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

The Vite dev server proxies `/api`, `/health`, and `/ws` to `localhost:8000`. If the backend runs somewhere else, set:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

The UI is organized around the legacy ad2web navigation model:

- Keypad: ADEMCO/DSC keypad, panel LCD with authentic phosphor-green styling, LEDs, sound mute, quick action commands (Arm Away, Arm Stay, Disarm with synthesized PIN), custom buttons, and command safety confirmation.
- Log: paged parsed event history and raw message history.
- Zones: categorized normal vs faulted zones with zone naming and enable/disable toggles.
- Diagnostics: raw messages, parsed events, current state JSON, connection/read-only status.
- Settings: device adapter configuration, encrypted Panel PIN, notifications (Webhook and SMTP email), keypad settings, users, WebAuthn Passkeys, password change, API tokens, export/import, and advanced audit/config views.
- Dark Mode: automatic OS-level theme detection with instant manual override (Auto / Light / Dark) in the top navigation bar.
- Progressive Web App (PWA): can be installed as a native app on iOS, iPadOS, Android, macOS, Windows, and Linux with full offline asset caching.

## Fake Adapter Behavior

The fake adapter starts connected and emits a ready panel message. It accepts keypad commands and updates state:

- `STAY` arms stay.
- `AWAY` arms away.
- `DISARM` disarms.
- `CHIME` toggles chime.
- `FAULT` faults zone 1.
- `RESTORE` restores zone 1.
- `F1` simulates fire.
- `F2` simulates panic.

It also emits periodic sample events so WebSocket updates and the event log can be exercised without hardware.

## Read-Only ser2sock Adapter

The ser2sock adapter is intentionally read-only for hardware validation. It opens a TCP connection and reads line-oriented AlarmDecoder messages. It does not send keypad commands, configuration commands, newlines, keepalives, discovery payloads, or any other bytes to the hardware connection.

Run it against a ser2sock endpoint:

```bash
cd backend
source .venv/bin/activate
ALARMDECODER_ADAPTER=ser2sock \
ALARMDECODER_SER2SOCK_HOST=alarmdecoder.local \
ALARMDECODER_SER2SOCK_PORT=10000 \
ALARMDECODER_SER2SOCK_TLS=false \
ALARMDECODER_READ_ONLY=true \
ALARMDECODER_ALLOW_COMMANDS=false \
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Safety behavior:

- Non-fake adapters default to `ALARMDECODER_READ_ONLY=true`.
- Hardware command mode also requires `ALARMDECODER_ALLOW_COMMANDS=true`.
- If `ALARMDECODER_READ_ONLY=true`, commands are always rejected even if `ALARMDECODER_ALLOW_COMMANDS=true`.
- `POST /api/keypad/command` returns `409 Conflict` when read-only mode is active.
- The frontend disables keypad controls when the effective config is read-only.
- The adapter reconnects with exponential backoff if ser2sock disconnects.
- The adapter does not modify AlarmDecoder, panel, Raspberry Pi, or ser2sock configuration.

Diagnostics:

- `GET /api/diagnostics/connection`
- `GET /api/diagnostics/raw-messages`
- `GET /api/diagnostics/events`
- `GET /api/config/effective`

Hardware validation checklist:

1. Start the backend with the read-only ser2sock command above.
2. Confirm `GET /api/config/effective` reports `adapter: "ser2sock"` and `read_only: true`.
3. Confirm `GET /api/diagnostics/connection` transitions through `connecting` to `connected`.
4. Confirm `GET /api/diagnostics/raw-messages` begins showing raw panel lines.
5. Confirm keypad buttons are disabled in the frontend.
6. Confirm a manual `POST /api/keypad/command` returns `409 Conflict`.

Do not run hardware validation with `ALARMDECODER_READ_ONLY=false`.

## Read-Only Serial Adapter

Use this for AD2USB, AD2PI, or AD2SERIAL hardware connected directly to the Raspberry Pi. The same safety defaults apply: serial adapters are read-only unless command mode is explicitly enabled.

```bash
cd backend
source .venv/bin/activate
ALARMDECODER_ADAPTER=serial \
ALARMDECODER_SERIAL_PATH=/dev/ttyUSB0 \
ALARMDECODER_SERIAL_BAUDRATE=115200 \
ALARMDECODER_PANEL_TYPE=ADEMCO \
ALARMDECODER_READ_ONLY=true \
ALARMDECODER_ALLOW_COMMANDS=false \
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Adapter aliases `ad2usb`, `ad2pi`, and `ad2serial` use the same serial implementation. Production serial access may require adding the `alarmdecoder-modern` user to the `dialout` group. Do not change panel or AlarmDecoder device configuration during read-only validation.

## Command-Enabled ser2sock Mode

Only enable this after read-only validation and only with explicit approval:

For local Mac development, prefer:

```bash
./scripts/create-hardware-admin.sh admin
./scripts/dev-hardware-commands.sh
```

For a manual backend-only start:

```bash
ALARMDECODER_ADAPTER=ser2sock \
ALARMDECODER_SER2SOCK_HOST=alarmdecoder.local \
ALARMDECODER_SER2SOCK_PORT=10000 \
ALARMDECODER_READ_ONLY=false \
ALARMDECODER_ALLOW_COMMANDS=true \
ALARMDECODER_AUTH_REQUIRED=true \
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Create an admin user first:

```bash
cd backend
source .venv/bin/activate
ALARMDECODER_DATABASE_URL=sqlite:///alarmdecoder-modern.db \
python -m app.cli create-admin --username admin
```

Operators and admins can send commands. Viewers cannot. Dangerous actions require explicit confirmation from the frontend and backend.

Custom keypad buttons are stored server-side per user. The frontend receives only button IDs, labels, and safety flags; custom command strings are not returned to the browser after creation and are still redacted in events, audit logs, diagnostics, and notifications.

## Setup, Users, And API Tokens

First-run state is available at `GET /api/setup/status`. The first admin can be created through `POST /api/setup/complete` when no users exist, or from the CLI:

```bash
cd backend
source .venv/bin/activate
python -m app.cli create-admin --username admin
```

Admins can manage users and API tokens from the settings UI. API tokens are stored as hashes and are displayed only once when created. Use them as bearer tokens:

```bash
curl -H "Authorization: Bearer ad2_..." http://localhost:8000/api/state
```

Settings export/import is available in the settings UI and through:

- `GET /api/admin/export`
- `POST /api/admin/import`

## Persistence

SQLite is used by default:

```bash
ALARMDECODER_DATABASE_URL=sqlite:///alarmdecoder-modern.db
```

The app creates missing tables safely at startup for first-run/dev use. Production installs should also run Alembic:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

Raw messages and parsed events have configurable retention:

```bash
ALARMDECODER_RAW_RETENTION_DAYS=14
ALARMDECODER_EVENT_RETENTION_DAYS=90
```

Back up SQLite:

```bash
python -m app.cli backup --output /tmp/alarmdecoder-modern-backup.db
```

Restore by stopping the service, replacing the database file, fixing ownership, and restarting the service.

Prune old raw/event history manually:

```bash
python -m app.cli prune-retention
```

## Notifications

Webhook notifications are configured by admins through the settings UI or `PUT /api/admin/notifications`. The settings UI can send a test notification. Notification payloads include event type, timestamp, and display-safe message only. Alarm codes, tokens, cookies, and provider secrets are not included.

## Raspberry Pi OS Production Install

The deployment templates are in `deploy/`.

Recommended layout:

- App: `/opt/alarmdecoder-modern`
- Data: `/var/lib/alarmdecoder-modern`
- Config: `/etc/alarmdecoder-modern`
- User: `alarmdecoder-modern`

Install outline:

```bash
sudo ./deploy/install.sh
sudo install -m 0640 -o root -g alarmdecoder-modern deploy/alarmdecoder-modern.env.example /etc/alarmdecoder-modern/alarmdecoder-modern.env
sudo nano /etc/alarmdecoder-modern/alarmdecoder-modern.env
sudo -u alarmdecoder-modern /opt/alarmdecoder-modern/backend/.venv/bin/python -m app.cli create-admin --username admin
sudo systemctl restart alarmdecoder-modern
sudo systemctl status alarmdecoder-modern
```

Update an existing install:

```bash
sudo ./deploy/update.sh
```

The service runs as a dedicated non-root user. Network access is enough for ser2sock. Direct serial adapters may require membership in the `dialout` group.

Build frontend assets manually for development:

```bash
cd frontend
npm ci
npm run build
```

FastAPI serves `frontend/dist` when built assets are present. Nginx can also serve the same directory using `deploy/nginx.conf.example`.

## Troubleshooting

- `/health` confirms the process is running.
- `/ready` reports adapter, connection, read-only, and command-mode status.
- `journalctl -u alarmdecoder-modern -f` shows service logs.
- `GET /api/diagnostics/connection` shows reconnect state and last connection error.
- `GET /api/diagnostics/raw-messages` confirms live ser2sock input in read-only mode.

Security details are in `docs/security-model.md`. Hardware validation steps are in `docs/hardware-validation-plan.md`.

## Tests

Backend tests use fake adapters, local fake TCP servers, and in-process fake serial objects. They do not connect to real hardware.

```bash
./scripts/test-harness.sh
```

The harness compiles the backend, runs pytest, builds the frontend, and validates deployment shell scripts. The tests assert that the read-only ser2sock adapter sends zero bytes to the fake server, reconnects after disconnect, and rejects keypad commands when read-only mode is active. Serial adapter tests use an in-process fake serial object; they do not open `/dev/tty*` or connect to hardware.

Parser coverage is fixture-driven from `backend/tests/fixtures/ser2sock-readonly-capture.txt`. Replace that file with a real read-only diagnostics capture to expand coverage without connecting tests to hardware.
