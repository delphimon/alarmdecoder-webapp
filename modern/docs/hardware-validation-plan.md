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

1. Create an admin or operator account.
2. Set:
   - `ALARMDECODER_READ_ONLY=false`
   - `ALARMDECODER_ALLOW_COMMANDS=true`
   - `ALARMDECODER_AUTH_REQUIRED=true`
3. Restart the service.
4. Sign in as `operator` or `admin`.
5. Send a low-risk keypad action first, such as chime toggle if appropriate for the panel.
6. Review audit logs and confirm submitted code values are redacted.

Do not modify ser2sock, AlarmDecoder, serial adapter, panel, or Raspberry Pi hardware configuration as part of validation.
