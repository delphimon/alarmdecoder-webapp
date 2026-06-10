# Modernization Plan

The new application should be a clean Python 3 implementation that treats the legacy app only as a behavioral reference.

## Recommended New Architecture

- Backend service:
  - Python 3.12+ FastAPI app.
  - Async REST API plus WebSocket endpoint.
  - SQLAlchemy 2.0 ORM with Alembic migrations.
  - Pydantic models for API contracts and settings validation.
  - Background task manager for device loop, notifications, exports, and scheduled checks.
- Frontend app:
  - React + TypeScript + Vite.
  - Single-page UI served as static assets by nginx or the FastAPI app in small installs.
  - WebSocket state store for live panel/keypad updates.
- Device layer:
  - Adapter interface first.
  - Fake/simulated adapter first.
  - Real serial adapter second.
  - Optional socket/ser2sock adapter third.
- Data store:
  - SQLite by default for Raspberry Pi appliance installs.
  - Postgres-compatible schema possible later, but not required initially.
- Process model:
  - One FastAPI/uvicorn service.
  - Optional nginx reverse proxy for TLS/static hosting.
  - Optional separate worker process only if notification/device work grows beyond one process.

## Backend Framework Recommendation

Use FastAPI.

Reasons:

- Native OpenAPI generation replaces the legacy static Swagger bundle.
- Pydantic models give explicit validation for device settings, notifications, and API payloads.
- WebSocket support can replace gevent Socket.IO without the old stack.
- Async request handling fits live device state, REST APIs, and notification/webhook IO.
- It remains Python-first and lightweight enough for Raspberry Pi OS.

Recommended backend modules:

- `app.main`: FastAPI app factory and lifespan startup/shutdown.
- `app.core.config`: environment/file settings.
- `app.db`: SQLAlchemy engine/session and migrations.
- `app.models`: database models.
- `app.schemas`: Pydantic request/response models.
- `app.auth`: sessions, password hashing, CSRF, API tokens.
- `app.device`: adapter interface, fake adapter, serial adapter, socket adapter.
- `app.panel_state`: normalized panel state reducer.
- `app.events`: event bus and event persistence.
- `app.notifications`: provider interface, rule matching, async delivery.
- `app.api`: REST routers.
- `app.ws`: websocket connection manager.
- `app.setup`: first-run setup flow and appliance mode checks.

## Frontend Framework Recommendation

Use React + TypeScript + Vite.

Recommended frontend structure:

- `src/api`: typed REST client.
- `src/ws`: websocket client with reconnect/backoff.
- `src/state`: panel state and auth stores.
- `src/features/keypad`: ADEMCO/DSC keypad components, beep/mute behavior, custom/special buttons.
- `src/features/setup`: setup wizard.
- `src/features/settings`: device, zones, notifications, users, diagnostics, backup.
- `src/features/logs`: event log and live log views.
- `src/components`: shared forms, dialogs, tables, status indicators.

UI priorities:

- Build the keypad as the first usable screen after login/setup.
- Preserve appliance-like clarity and responsiveness.
- Use modern accessible controls instead of image-only buttons where possible, while keeping the familiar alarm keypad layout.
- Keep emergency/special actions protected by confirmation dialogs.

## Device Adapter Strategy

Start with a strict adapter interface:

- `open()`, `close()`, `is_open`.
- `send_keys(keys: str)`.
- `get_configuration()` and `set_configuration(...)`.
- `reboot()` where supported.
- async event stream yielding structured messages/events.

Phase 1: fake adapter.

- Deterministic simulation for development and tests.
- Configurable panel mode.
- Emits sample panel messages and state transitions.
- Responds to keypresses with plausible beeps/text/state changes.
- Simulates zone fault/restore, alarm/fire/panic, power loss/restore, low battery, LRR, RFX, EXP, and AUI.
- Powers automated frontend and backend tests without hardware.

Phase 2: real serial adapter.

- Use pyserial or a maintained AlarmDecoder Python 3-compatible library only after validating maintenance and behavior.
- Isolate all library-specific parsing behind the adapter.
- Normalize raw library callbacks into app-owned event schemas.
- Add robust reconnect, timeout, and backpressure behavior.

Phase 3: network/socket adapter.

- Support remote AlarmDecoder or ser2sock-like TCP endpoint.
- Treat TLS/mTLS as explicit config.
- Do not make ser2sock management a core requirement.

## Deployment Strategy For Current Raspberry Pi OS

Recommended appliance deployment:

- Raspberry Pi OS current stable, 64-bit where hardware allows.
- Python 3 virtualenv or packaged app under `/opt/alarmdecoder-webapp`.
- systemd service running as a dedicated unprivileged user, for example `alarmdecoder`.
- Add the service user to `dialout` for serial device access.
- Store runtime data under `/var/lib/alarmdecoder-webapp`.
- Store logs under `/var/log/alarmdecoder-webapp` or journald.
- Store config under `/etc/alarmdecoder-webapp`.
- SQLite database under the data directory.
- nginx optional:
  - terminate TLS.
  - serve frontend static assets.
  - proxy `/api` and `/ws` to uvicorn.
- Avoid root service execution.
- Avoid direct editing of host networking files. Prefer documented OS tools or a separate privileged helper if appliance network management is required.
- Provide install/update as:
  - systemd unit.
  - pinned Python dependencies.
  - frontend build artifact.
  - Alembic migration command.
  - optional backup/restore command.

## Test Strategy

Backend:

- Unit tests for panel state reducer, event normalization, adapter contract, notification rule matching, message templates, zone filtering, and auth/token logic.
- Integration tests with SQLite test DB and FastAPI TestClient.
- WebSocket tests using the fake adapter.
- Migration tests for schema creation and upgrade.
- Contract tests for REST response schemas.

Frontend:

- Component tests for keypad layout, status indicators, confirmation dialogs, setup wizard, notification forms, and settings forms.
- State/store tests for websocket events and reconnect behavior.
- Playwright end-to-end tests against fake adapter:
  - first-run setup.
  - login/logout.
  - keypad rendering.
  - keypress send.
  - live message/state update.
  - notification rule CRUD.
  - zone CRUD.

Hardware:

- Manual and automated smoke tests on real Raspberry Pi hardware with AD2USB/AD2PI when available.
- Serial disconnect/reconnect tests.
- Permission tests for `dialout`.
- Long-running soak test for websocket clients, event logging, and notification queue behavior.

Security:

- Auth/authorization tests for every admin route.
- CSRF tests for browser form mutations.
- API token scope tests.
- Secret redaction tests for logs/API responses.
- Backup import validation tests.

## Phased Implementation Plan

### Phase 0: Project Skeleton

- Create a new Python 3/FastAPI backend and React/Vite frontend.
- Add linting, formatting, tests, CI, and local dev scripts.
- Add SQLite/Alembic baseline.
- Add basic auth/session scaffolding.

### Phase 1: Fake Adapter And Live Keypad

- Define device adapter interface and event schemas.
- Implement fake adapter.
- Implement panel state reducer and event bus.
- Build WebSocket endpoint.
- Build React keypad for ADEMCO and DSC.
- Implement keypress send and beep/mute behavior.

### Phase 2: Setup, Users, And Core Settings

- First-run setup wizard.
- Admin account creation.
- Login/logout/password change.
- Device configuration forms.
- Diagnostics page backed by fake adapter.
- API token management.

### Phase 3: Events, Zones, And Logs

- Event persistence.
- Zone CRUD.
- Event log view.
- REST API for state, send, zones, and logs.
- Fake adapter scenarios for zone/alarm/fire/panic/power/battery events.

### Phase 4: Notifications

- Notification rule model.
- Email and custom webhook providers first.
- Message templates with validation/preview.
- Async delivery queue with retries/timeouts.
- Add Pushover, Twilio, Matrix, and optional UPnP push as needed.

### Phase 5: Real Device Adapter

- Evaluate AlarmDecoder Python 3 library support or implement a minimal serial parser/sender behind the adapter.
- Add serial adapter.
- Add reconnect and health reporting.
- Test with real AD2USB/AD2PI/AD2SERIAL.
- Add optional network/socket adapter.

### Phase 6: Appliance Deployment

- systemd unit and install docs.
- nginx sample config.
- data/config/log directory migration.
- backup/restore command.
- Raspberry Pi OS smoke tests.

### Phase 7: Legacy Feature Review

- Decide whether to implement camera support, firmware updates, port forwarding, host network controls, and certificate UI.
- Keep these optional and isolated from the core keypad/notification app.
- Drop unneeded profile/social/OpenID/git-update behavior.
