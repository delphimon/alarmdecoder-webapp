# Security Model

AlarmDecoder Modern treats keypad commands as security-sensitive actions.

## Defaults

- Non-fake adapters default to `ALARMDECODER_READ_ONLY=true`.
- Hardware command mode requires `ALARMDECODER_READ_ONLY=false` and `ALARMDECODER_ALLOW_COMMANDS=true`.
- If read-only is true, commands are rejected even when command mode is enabled.
- Authentication is required by default for non-fake adapters.

## Roles

- `viewer`: can view state, diagnostics, and history.
- `operator`: can send allowed keypad commands when command mode is enabled.
- `admin`: can operate the panel and manage users, settings, zones, notifications, and audit views.

## Alarm Codes

Submitted keypad values are never written to frontend storage, URLs, raw diagnostics, event messages, audit details, structured logs, or notification payloads. Backend audit and event entries store only redacted command metadata such as length and whether digits were present.

Custom keypad buttons keep their command strings server-side. The button list API returns labels, IDs, and safety flags only. Sending a custom button submits the stored command by ID through the same command service and redaction path as manual keypad commands.

## Browser Sessions

The backend uses an HttpOnly, SameSite=strict session cookie containing a signed JWT. Mutating browser requests must include the `X-CSRF-Token` header matching the non-HttpOnly CSRF cookie issued by `/api/auth/login` and `/api/auth/me`. Bearer-token clients are exempt for tests and automation.

Keep the app on a trusted local network. Use a reverse proxy with TLS if exposing beyond localhost.

API tokens are generated once, stored only as SHA-256 hashes, and can be revoked by admins. Token responses show the raw token only at creation time.

## Notifications

Notifications are display-safe event summaries. Webhook payloads contain event type, timestamp, and message only. Provider secrets are redacted before persistence and never included in notifications.

## Hardware Safety

Tests use fake adapters, local fake TCP servers, or in-process fake serial objects only. Live hardware validation must use read-only mode unless a human explicitly changes the environment file to command mode. The serial adapter follows the same command gate as ser2sock and must not be used to validate writes against real hardware by default.
