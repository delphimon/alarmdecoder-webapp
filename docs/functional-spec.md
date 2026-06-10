# Functional Specification

This specification identifies user-facing behavior from the legacy app that should be preserved, redesigned, or dropped in a modern implementation. It intentionally describes behavior, not a Python 2 port.

## User-Facing Features To Preserve

- Web keypad for AlarmDecoder-connected panels.
- Support for ADEMCO and DSC keypad layouts.
- Real-time panel display with two LCD-style text lines.
- Real-time armed, ready, and chime indicators.
- Keypress sending for digits, `*`, `#`, function/special keys, and custom buttons.
- Audible and visual beep feedback, with a user-controlled mute setting.
- Confirmation prompts before emergency/special/custom dangerous sends.
- Panel state summary API: power, ready, alarming, bypassed, armed, armed stay, fire, battery trouble, panic, chime, relay status, faulted zones, and last message.
- Zone names/descriptions for human-readable event output.
- Event log/history view.
- Notification rules for alarm/security events.
- Initial setup wizard for device connection, panel configuration, device test, and admin account creation.
- Basic admin/user management.
- Backup/export and import of appliance settings.
- Diagnostics view for device firmware, serial number, flags, config bits, address, masks, emulation, and panel mode.

## Admin And Settings Features

Preserve with modernized implementation:

- First-run setup state and enforced setup wizard.
- Device setup:
  - device type: AD2USB, AD2PI, AD2SERIAL, network.
  - local serial path and baud rate.
  - network host/port and optional TLS.
  - panel mode: ADEMCO or DSC.
  - keypad address, address mask, internal address mask.
  - LRR, zone expander, relay expander, and deduplication options.
- Device test flow:
  - open connection.
  - save/read configuration.
  - send test keypress.
  - receive message.
- User management:
  - create, edit, disable/delete users.
  - admin vs standard user roles.
  - login history and failed login review.
- API keys or replacement token management.
- Zone CRUD and import.
- Custom keypad button CRUD per user.
- Special keypad button configuration.
- System email configuration.
- Notification provider configuration and test send.
- Notification message template editing.
- Settings export/import.
- Device diagnostics.

Redesign carefully:

- Host networking, hostname, reboot, shutdown, and port forwarding should be separated behind explicit appliance-admin permissions and probably disabled by default on non-appliance installs.
- Git branch switching and self-update should be replaced with package/container update mechanisms.
- Certificate management should be simplified around standard TLS/mTLS config instead of ad hoc database-backed private key storage.
- ser2sock management should become an optional adapter mode, not a required core workflow.

## Keypad Behavior

- The keypad page must subscribe to live panel messages.
- Panel text is displayed as up to two 16-character lines. Cursor location, when available, should be represented visually.
- On each panel message:
  - update text lines.
  - update armed LED from away/home armed status.
  - update ready LED from ready status.
  - update chime indicator from chime status.
  - if `beeps` is present, visually flash the display and play the matching beep sound unless muted.
- Beep support should cover 1 through 7 beeps.
- Mute should persist per browser.
- Key controls should work by mouse, touch, and keyboard.
- Pressed buttons should show immediate visual feedback.
- ADEMCO layout:
  - digits 0-9, `*`, `#`.
  - F1-F4/special keys.
- DSC layout:
  - digits 0-9, `*`, `#`.
  - navigation/cursor keys where relevant.
  - stay, away, chime, reset, exit special controls.
- Emergency/special/custom buttons should require explicit confirmation before sending.
- Custom buttons are per-user, have a label and a code/string to send, and appear in an accessible custom button menu.

## Event And State Behavior

- Raw panel/device messages should be normalized into typed events and current panel state.
- Supported events:
  - arm, disarm, power changed, alarm, alarm restored, fire changed, bypass, boot, config received, zone fault, zone restore, low battery, panic, LRR, ready changed, chime changed, RFX, EXP, AUI.
- Event processing should:
  - update in-memory current panel state.
  - persist a log entry.
  - broadcast real-time events to connected clients.
  - trigger matching notifications.
- Zone event messages should include configured zone name where available, otherwise show an unnamed fallback.
- LRR, RFX, EXP, and AUI events should preserve useful structured fields instead of forcing every consumer to parse text.
- Device open/close state should be broadcast to clients.
- Automatic reconnect should attempt to restore the device connection after close/failure.
- A fake/simulated AlarmDecoder adapter must be implemented before real serial/network adapters. It should simulate:
  - open/close.
  - keypress receipt.
  - panel messages with text, ready, armed, chime, and beep fields.
  - zone fault/restore events.
  - alarm, fire, panic, power, battery, LRR, RFX/EXP/AUI sample events.
  - test flow responses.

## Notification Behavior

- Users/admins can create multiple notification rules.
- Rules have:
  - type/provider.
  - description.
  - enabled/disabled state.
  - subscriptions to event types.
  - optional zone filter for zone fault/restore/bypass.
  - optional active time window.
  - optional delay for zone-related notifications.
  - optional suppression of transient zone notifications.
- Default provider set to preserve at least behaviorally:
  - email.
  - Pushover.
  - Twilio SMS.
  - custom HTTP webhook.
  - Matrix.
  - UPnP push/event subscription if external integrations still require it.
- Providers to reconsider:
  - Prowl and Growl are legacy-era integrations and should be optional only if there is clear current demand.
  - TwiML callback behavior should be redesigned as a webhook-compatible provider if preserved.
- Editable message templates should remain, but the new system should validate placeholders and preview sample output.
- Notification sends should be asynchronous, observable, and bounded by timeouts/retries.
- The event log should remain independent from user-created notification rules so every event is still recorded.

## User And Account Behavior

- First setup creates the initial admin account.
- Browser users log in with username/email and password.
- Passwords must be securely hashed using a current password hashing scheme.
- Users can change their own password.
- Admins can manage users and roles.
- Failed login attempts and successful login history should be recorded.
- Password reset may be preserved through email, but should use expiring, single-use reset tokens.
- API access should be represented by per-user tokens with creation, revocation, last-used metadata, scope/role, and secure one-time display.

## Features To Drop Or Redesign

Drop unless explicitly needed:

- Python 2 runtime, Flask-Script, gevent-socketio, Flask-OpenID, legacy Bootstrap/jQuery UI/DataTables asset bundle.
- OpenID login.
- Social/following/user-detail profile fields unrelated to appliance operation.
- In-app git branch switching and git pull updates.
- Bundled Swagger UI copy; generate OpenAPI from the FastAPI app instead.
- Direct support for old browser-specific UI hacks.

Redesign:

- Host network editing through `/etc/network/interfaces`; current Raspberry Pi OS uses newer networking stacks and the app should not assume this file.
- Reboot/shutdown/network/hostname operations; expose only in appliance mode with explicit confirmation and audit logging.
- UPnP router port forwarding; disable by default because it exposes a security system to the internet.
- API authentication; replace query-string API keys with bearer tokens and scopes.
- Certificate/private key storage; prefer file/env/secret-store-backed TLS config with minimal DB metadata.
- Camera polling; either remove from core or implement as an optional integration with safe credential storage.
- Backup import/export; use a versioned JSON export format with validation and dry-run preview.
- Notification provider secrets; store encrypted at rest or in an OS secret file with strict permissions.
- Firmware update workflow; separate from normal app runtime and guard with device compatibility checks.
