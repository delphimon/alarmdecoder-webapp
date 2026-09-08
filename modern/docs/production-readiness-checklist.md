# Production Readiness Checklist

This checklist separates repository-complete work from on-device validation. Repository items are complete when the code, tests, and deployment artifacts exist in this repo. Deployment items must be completed on the target Raspberry Pi and are intentionally not marked complete here.

## Repository Complete

- [x] Non-fake adapters default to read-only mode.
- [x] `ALARMDECODER_ALLOW_COMMANDS=true` is required before command mode can write to ser2sock or serial hardware.
- [x] `ALARMDECODER_READ_ONLY=true` wins over command mode and always rejects commands.
- [x] Command submission goes through a backend service layer.
- [x] Dangerous actions require explicit confirmation.
- [x] Command cooldown protection exists.
- [x] Viewer/operator/admin roles exist.
- [x] Local login/logout and signed HttpOnly session cookie support exist.
- [x] CSRF protection exists for cookie-authenticated mutating routes.
- [x] Admin creation CLI exists: `python -m app.cli create-admin --username admin`.
- [x] Admin APIs exist for users, settings, zones, notifications, and audit logs.
- [x] First-run setup status/completion APIs exist.
- [x] Per-user custom keypad buttons are stored server-side and send by ID without exposing command values in normal button list responses.
- [x] API tokens are represented by hashed, one-time-display bearer tokens with revocation.
- [x] Settings export/import APIs exist with dry-run support.
- [x] Submitted keypad values are redacted from events, audit logs, and notifications.
- [x] Tests verify command rejection, read-only precedence, fake-server-only command writes, role enforcement, CSRF, retention, migrations, and alarm-code redaction.
- [x] SQLite schema creates safely when missing.
- [x] Alembic initial migration exists and is tested.
- [x] SQLite includes parsed events, raw messages, zones, app settings, notification settings, users, and audit log tables.
- [x] Raw and event retention settings exist.
- [x] `/health` and `/ready` endpoints exist.
- [x] Frontend production build succeeds.
- [x] FastAPI serves `frontend/dist` when built assets are present.
- [x] systemd service template exists for `/opt/alarmdecoder-modern`.
- [x] Environment file template exists for `/etc/alarmdecoder-modern`.
- [x] Install script creates `/opt/alarmdecoder-modern`, `/var/lib/alarmdecoder-modern`, and `/etc/alarmdecoder-modern`.
- [x] Install script creates a dedicated `alarmdecoder-modern` Linux user.
- [x] Install script builds frontend static assets.
- [x] Update script applies dependencies, migrations, and frontend build.
- [x] Optional nginx config exists.
- [x] CI runs backend tests and frontend build checks.
- [x] Security model, hardware validation plan, and deployment docs exist.
- [x] Local serial adapter exists for AD2USB, AD2PI, and AD2SERIAL deployments.
- [x] Frontend uses the legacy `1beep.wav` through `7beep.wav` assets and only plays them for incoming panel message beep fields when sound is enabled.
- [x] Local ser2sock simulator exists for Mac development without hardware.
- [x] `scripts/test-harness.sh` runs safe backend, frontend, and deployment checks without hardware access.
- [x] Full 20-character AlarmDecoder bitfield flag parsing with low battery, check zones, and AC power states.
- [x] Server-side PIN keystroke synthesis for Honeywell/ADEMCO Vista and DSC panels.
- [x] HKDF-SHA256 and Fernet symmetric encryption for stored panel PIN.
- [x] WebAuthn / FIDO2 passkey registration, authentication, and credential management.
- [x] SQLite WAL (Write-Ahead Logging) mode and thread-pool decoupled event persistence.
- [x] Async Webhook and SMTP email notification providers.
- [x] Accessible dark mode design system with OS-level auto-detection and 3-way manual toggle.
- [x] Progressive Web App (PWA) manifest, service worker, and mobile meta tags.
- [x] Native `<dialog>` accessible modals replacing `window.confirm` and `window.prompt`.
- [x] Dialout group automation in deploy scripts for unprivileged serial device access.
- [x] GitHub Actions automated release pipeline with pre-built asset packaging.
- [x] Dev startup scripts with fail-fast health polling and process death detection.

## Raspberry Pi Deployment Validation

- [ ] App installed under `/opt/alarmdecoder-modern`.
- [ ] Data directory exists at `/var/lib/alarmdecoder-modern`.
- [ ] Config directory exists at `/etc/alarmdecoder-modern`.
- [ ] `/etc/alarmdecoder-modern/alarmdecoder-modern.env` reviewed and edited.
- [ ] `ALARMDECODER_READ_ONLY=true` for first hardware boot.
- [ ] `ALARMDECODER_ALLOW_COMMANDS=false` until command validation is explicitly approved.
- [ ] `ALARMDECODER_SESSION_SECRET` replaced with a long random value.
- [ ] Admin account created with `python -m app.cli create-admin --username admin`.
- [ ] Service runs as `alarmdecoder-modern`, not root.
- [ ] systemd service enabled and healthy.
- [ ] `/health` and `/ready` monitored.
- [ ] Journald logs reviewed after startup.
- [ ] Nginx reverse proxy tested if used.
- [ ] SQLite database present in `/var/lib/alarmdecoder-modern`.
- [ ] Backup process tested with `sqlite3 /var/lib/alarmdecoder-modern/alarmdecoder-modern.db ".backup backup.db"`.
- [ ] Raw/event retention values reviewed.
- [ ] Read-only hardware validation completed against `alarmdecoder.local:10000`.
- [ ] Local simulator validation completed on the development Mac.
- [ ] Alarm codes verified absent from logs, events, diagnostics, audit entries, and notifications after command-mode dry run against a fake server or approved test panel.
- [ ] Serial access, if used, is granted through the `dialout` group rather than running the service as root.
