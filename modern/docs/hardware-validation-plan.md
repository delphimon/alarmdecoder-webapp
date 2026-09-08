# Hardware Validation Plan

## Local Simulator Validation

Run this before any live hardware validation:

1. Start `./scripts/run-ser2sock-simulator.sh`.
2. Start the backend with:
   - `ALARMDECODER_ADAPTER=ser2sock`
   - `ALARMDECODER_SER2SOCK_HOST=127.0.0.1`
   - `ALARMDECODER_SER2SOCK_PORT=10000`
   - `ALARMDECODER_READ_ONLY=true`
   - `ALARMDECODER_ALLOW_COMMANDS=false`
3. Start `./scripts/run-frontend-dev.sh`.
4. Confirm `/api/diagnostics/raw-messages` shows simulator fixture lines.
5. Confirm keypad controls are disabled.
6. Confirm `backend/.simulator-writes.bin` is absent or empty.

## Read-Only Validation

1. Configure `/etc/alarmdecoder-modern/alarmdecoder-modern.env` for network ser2sock with:
   - `ALARMDECODER_ADAPTER=ser2sock`
   - `ALARMDECODER_SER2SOCK_HOST=alarmdecoder.local`
   - `ALARMDECODER_SER2SOCK_PORT=10000`
   - `ALARMDECODER_READ_ONLY=true`
   - `ALARMDECODER_ALLOW_COMMANDS=false`
2. Or configure direct serial hardware with:
   - `ALARMDECODER_ADAPTER=serial`
   - `ALARMDECODER_SERIAL_PATH=/dev/ttyUSB0`
   - `ALARMDECODER_SERIAL_BAUDRATE=115200`
   - `ALARMDECODER_READ_ONLY=true`
   - `ALARMDECODER_ALLOW_COMMANDS=false`
3. Start the service.
4. Verify `/api/diagnostics/connection` reaches `connected`.
5. Verify `/api/diagnostics/raw-messages` shows live messages.
6. Confirm keypad buttons are disabled.
7. Confirm `POST /api/keypad/command` returns a rejection.

## Command-Enabled Validation

Only run this after read-only validation and only against a controlled test panel or with explicit approval.

1. Create an admin or operator account using `./scripts/create-hardware-admin.sh admin`.
2. Set:
   - `ALARMDECODER_READ_ONLY=false`
   - `ALARMDECODER_ALLOW_COMMANDS=true`
   - `ALARMDECODER_AUTH_REQUIRED=true`
3. Start or restart the service (or use `./scripts/dev-hardware-commands.sh`).
4. Sign in as `operator` or `admin`.
5. Configure panel PIN in **Settings** > **Panel PIN**.
6. Send a low-risk keypad action first:
   - For Honeywell Vista panels: trigger **Chime** or disarm sequence (`{pin}1`).
   - For DSC panels: trigger keypad digit or chime.
7. Review audit logs (`/api/audit`) and event logs (`/api/history/events`) to confirm submitted PIN and keypad values are completely redacted (e.g. `[REDACTED: 4 chars]`).

## Bitfield Flag & Status Validation

1. Observe the live panel LCD and status LEDs on the web interface.
2. Verify bitfield flag parsing reflects actual panel states:
   - Armed Away / Armed Stay LEDs light up appropriately.
   - AC power indicator reflects panel power transformer state.
   - Battery low warning displays if the backup battery is disconnected or low.
   - Zone faults reflect open sensors immediately.
3. Check `/api/state` or WebSocket snapshot to ensure `flags` dictionary contains parsed bitfields (`ready`, `armed_away`, `armed_stay`, `ac_power`, `battery_low`, `fire`, `check_zones`, `chime`).

## Passkey & Browser Validation

1. From the web UI on a secure context (https or localhost/127.0.0.1):
2. Navigate to **Settings** > **Security & Passkeys**.
3. Click **Add Passkey** and complete the biometric prompt (Touch ID / Face ID / security key).
4. Sign out and sign in using **Sign in with Passkey** with zero password entry required.

Do not modify ser2sock, AlarmDecoder, serial adapter, panel, or Raspberry Pi hardware configuration as part of validation.
