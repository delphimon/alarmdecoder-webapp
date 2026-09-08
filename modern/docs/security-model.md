# Security Model

AlarmDecoder Modern treats keypad commands and panel credentials as security-sensitive actions.

## Defaults

- Non-fake adapters default to `ALARMDECODER_READ_ONLY=true`.
- Hardware command mode requires `ALARMDECODER_READ_ONLY=false` and `ALARMDECODER_ALLOW_COMMANDS=true`.
- If read-only is true, commands are rejected even when command mode is enabled.
- Authentication is required by default for non-fake adapters.
- Weak session secrets (< 32 characters) trigger prominent startup warnings.

## Roles

- `viewer`: can view state, diagnostics, and history.
- `operator`: can send allowed keypad commands when command mode is enabled.
- `admin`: can operate the panel and manage users, settings, zones, notifications, passkeys, and audit views.

## Alarm Codes & Panel PIN Encryption

Submitted keypad values and panel PINs are never written to frontend storage, URLs, raw diagnostics, event messages, audit details, structured logs, or notification payloads.

### Server-Side PIN Encryption
- When configured via `POST /api/settings/pin`, the panel PIN is encrypted at rest using Fernet (AES-128-CBC with HMAC-SHA256 authentication).
- The encryption key is derived from `ALARMDECODER_SESSION_SECRET` using HKDF-SHA256 (`cryptography.hazmat.primitives.kdf.hkdf.HKDF`) with fixed application salt and context strings.
- The stored PIN is **never returned** by the API: `GET /api/settings/pin` returns only `{ "configured": true/false }`.
- When an operator or admin triggers an action (such as Arm Away, Arm Stay, or Disarm), the backend decrypts the PIN transiently in memory, synthesizes the panel-specific keystroke sequence, transmits it to the hardware adapter, and immediately discards the plaintext.

### Custom Keypad Buttons
Custom keypad buttons keep their command strings server-side. The button list API returns labels, IDs, and safety flags only. Sending a custom button submits the stored command by ID through the same command service and redaction path as manual keypad commands.

## WebAuthn Passkeys

AlarmDecoder Modern supports FIDO2 / WebAuthn passkey authentication:
- **Zero Shared Secrets**: The server never stores passwords or private keys for passkeys. Authentication relies on public-key cryptography (ES256 / RS256).
- **Phishing & MITM Resistance**: Passkeys are cryptographically bound to the application's origin/relying party ID (`rp_id`).
- **Replay Protection**: Authenticator sign counters are tracked monotonically in the `passkey_credentials` database table to detect cloned authenticators.
- **Biometric Integration**: Users can register Touch ID, Face ID, Windows Hello, Android Biometrics, or USB/NFC hardware security keys (e.g., YubiKey) for fast 1-tap sign-in.

## Browser Sessions & CSRF Architecture

- **Session Cookie**: The backend issues an `HttpOnly`, `SameSite=Strict`, `Path=/` cookie (`ad2_session`) containing a signed HS256 JWT.
- **CSRF Token Cookie**: A separate, non-HttpOnly cookie (`ad2_csrf`) is issued on authentication.
- **Double-Submit Enforcement**: For any mutating request (POST, PUT, PATCH, DELETE) using cookie authentication, the client must transmit the CSRF token in the `X-CSRF-Token` HTTP header. The backend verifies cryptographic equality before processing the request.
- **API Bearer Tokens**: Bearer-token clients (`Authorization: Bearer ad2_...`) bypass the CSRF check for programmatic and headless integrations. API tokens are stored as SHA-256 hashes and can be revoked by admins at any time.

## Notification Safety & Secret Redaction

- Notifications are display-safe event summaries.
- Webhook and SMTP notification payloads contain event type, timestamp, and message only.
- Sensitive fields in notification configs (`password`, `secret`, `hmac_secret`, `api_key`, `token`) are automatically redacted before persistence and masked in all API responses.

## Hardware Safety & Dialout Isolation

- Tests use fake adapters, local fake TCP servers, or in-process fake serial objects only.
- Live hardware validation must use read-only mode unless an operator explicitly changes the environment file to command mode.
- Direct serial hardware access (AD2USB, AD2PI, AD2SERIAL) runs under the unprivileged `alarmdecoder-modern` system user with `dialout` group membership; root execution is forbidden.
