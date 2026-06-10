# Legacy Source Analysis

This document summarizes the legacy AlarmDecoder web application as a behavioral reference only. The application is a Python 2.7 Flask app with gevent Socket.IO, SQLAlchemy, Jinja templates, and direct Raspberry Pi host/device management.

## Architecture

- The app factory is `ad2web/app.py:create_app`. It creates a Flask application, registers blueprints, initializes extensions, wraps the WSGI app for reverse-proxy headers, creates a separate Socket.IO server, and attaches a long-lived `Decoder` object to `app.decoder`.
- `ad2web/decoder.py:Decoder` is the central runtime coordinator. It owns the AlarmDecoder device object, websocket broadcasting, reconnect/restart flags, updater state, notification system, camera poller, discovery server, UPnP thread, export scheduler, and version checker.
- Persistence uses Flask-SQLAlchemy against SQLite by default at `/opt/alarmdecoder-webapp/instance/db.sqlite`, with Alembic migrations in `alembic/versions`.
- UI is server-rendered Jinja plus jQuery/Bootstrap and template-included JavaScript. The keypad is mostly client-side behavior driven by websocket events.
- The app assumes a mutable appliance environment: it writes under `/opt/alarmdecoder-webapp/instance`, edits host/network files, manages `ser2sock`, starts/stops services, and can reboot/shutdown the host.

## Entry Points

- `manage.py`
  - `python manage.py run`: starts the debug/reloader path and runs the Socket.IO server.
  - `python manage.py initdb`: drops/recreates all tables, stamps Alembic head, and seeds default notification messages.
- `wsgi.py`
  - Imports `create_app`/`init_app`, inserts `/opt/alarmdecoder` into `sys.path`, initializes the device runtime, and starts Socket.IO in a background thread for WSGI deployment.
- `ad2web/app.py:init_app`
  - Checks that the `settings` table exists.
  - Initializes and starts the `Decoder`.
  - Installs a SIGINT handler to stop socket/device threads.
- Deployment examples use gunicorn with `socketio.sgunicorn.GeventSocketIOWorker` and nginx as TLS/static/reverse proxy.

## Services And Processes

- Flask web app: request/response pages and REST API.
- Socket.IO server: listens on `AD_LISTENER_PORT` or `5000`, resource `/socket.io`, namespace `/alarmdecoder`.
- `DecoderThread`: every 5 seconds attempts device reconnects and handles app restart requests.
- `VersionChecker`: checks webapp/API/firmware updates on a configured interval.
- `CameraChecker`: polls configured camera JPEG URLs and writes current images.
- `NotificationThread`: watches asynchronous notification futures and processes delayed/suppressed zone notifications.
- `ExportChecker`: periodically exports settings database content, optionally stores files locally and emails backups.
- `DiscoveryServer`: provides discovery behavior; static UPnP metadata exists under `ad2web/static`.
- `UPNPThread`: optional miniupnpc-managed port forwarding.
- `ser2sock`: optional external serial-to-socket process managed through config files and signals.

## Hardware And Device Communication

- Supported device families are AD2USB, AD2PI, and AD2SERIAL. The setup flow distinguishes local serial devices from network devices.
- Local serial paths default to:
  - AD2USB: `/dev/ttyUSB0`
  - AD2PI: `/dev/serial0`
  - AD2SERIAL: `/dev/ttyS0`
- Default baud rates are 115200 for AD2USB/AD2PI and 19200 for AD2SERIAL.
- Device access uses the legacy `alarmdecoder` Python package:
  - `SerialDevice` for local serial.
  - `SocketDevice` for network/ser2sock access.
  - Optional SSL uses certificates stored in the database and exported for ser2sock.
- Device configuration includes panel mode, keypad address, address mask, internal address mask, LRR emulation, zone expander emulation, relay expander emulation, and deduplication.
- Runtime event binding maps AlarmDecoder events to internal event IDs: arm, disarm, power change, alarm, alarm restored, fire, bypass, boot, LRR, ready, chime, config received, zone fault/restore, low battery, panic, RFX, EXP, and AUI.
- Keypad send paths:
  - Websocket `keypress` sends keypad digits/symbols or special key constants to `device.send`.
  - REST `POST /api/v1/alarmdecoder/send` sends a `keys` string, expanding tokens like `<F1>`, `<PANIC>`, and `<S1>` through `<S8>`.
  - Zone fault/restore API sends `L{zone}1` and `L{zone}0`, intended only for emulated zones.

## Web Routes

Primary server-rendered routes:

- Frontend:
  - `/`: landing page or redirect to keypad.
  - `/login`, `/logout`, `/reauth`, `/change_password`, `/reset_password`, `/help`, `/license`.
- Setup wizard:
  - `/setup/`, `/setup/type`, `/setup/local`, `/setup/network`, `/setup/sslclient`, `/setup/sslserver`, `/setup/device`, `/setup/test`, `/setup/account`, `/setup/complete`.
- Keypad:
  - `/keypad/`, `/keypad/legacy`, `/keypad/button_index`, `/keypad/specials`, `/keypad/create_button`, `/keypad/edit/<id>`, `/keypad/remove/<id>`.
- Settings/admin:
  - `/settings/`, `/settings/profile`, `/settings/password`, `/settings/host`, `/settings/hostname`, `/settings/network/<device>`, `/settings/reboot`, `/settings/shutdown`, `/settings/configure_exports`, `/settings/export`, `/settings/git`, `/settings/import`, `/settings/diagnostics`, `/settings/advanced`, `/settings/port_forward`, `/settings/configure_updater`, `/settings/configure_system_email`.
  - User admin is also mounted under `/settings`: `/settings/users`, `/settings/users/failed_logins`, `/settings/user/create`, `/settings/user/<id>`, `/settings/user/remove/<id>`.
- Zones:
  - `/settings/zones/`, `/settings/zones/create`, `/settings/zones/edit/<id>`, `/settings/zones/remove/<id>`, `/settings/zones/import`.
- Notifications:
  - `/notifications/`, create/edit/copy/remove/toggle/review, zone filters, and editable notification message templates.
- Logs:
  - `/log/`, `/log/live`, `/log/delete`, `/log/alarmdecoder`, `/log/alarmdecoder/get_data/<lines>`, `/log/retrieve_events_paging_data`.
- API settings and REST API:
  - `/api/`, `/api/api_doc`, `/api/swagger`, `/api/keys`, key generation/disable routes.
  - `/api/v1/alarmdecoder`, `/send`, `/event`, `/reboot`, `/configuration`.
  - `/api/v1/zones`, `/zones/<id>`, `/zones/<id>/fault`, `/zones/<id>/restore`.
  - `/api/v1/notifications`, `/notifications/<id>`.
  - `/api/v1/cameras`, `/cameras/<id>`.
  - `/api/v1/users`, `/users/<id>`.
  - `/api/v1/system`, `/system/reboot`, `/system/shutdown`.
- Certificates:
  - `/settings/certificates/`, generate, view/download/revoke, CA generate/revoke.
- Cameras:
  - `/cameras/`, `/cameras/camera_list`, create/edit/remove.
- Updater:
  - `/update/`, `/update/update`, `/update/restart`, `/update/checkavailable`, `/update/check_for_updates`, `/update/update_firmware`, `/update/firmware`.

## Websocket And Socket.IO Behavior

- Socket.IO route is mounted through the Flask blueprint at `/socket.io/<path>`, with namespace `/alarmdecoder`.
- The client wrapper in `ad2web/static/js/alarmdecoder.js` connects to `/alarmdecoder` with reconnect enabled.
- Server broadcast channels:
  - `message`: AlarmDecoder panel, LRR, ready, chime, RFX, EXP, and AUI messages. Payload includes `message` and `message_type`.
  - `event`: normalized event kwargs from AlarmDecoder event callbacks.
  - `device_open` and `device_close`.
  - `test`: setup/device test results for open/config/send/receive.
  - `firmwareupload`: firmware update stage/progress/error events.
- Client events sent to server:
  - `keypress`: sends keypad digit/symbol/special key data to the AlarmDecoder device.
  - `test`: runs device setup tests.
  - `firmwareupload`: performs a firmware upload workflow.
- Socket authentication is session-based. During `recv_connect`, a user session or incomplete setup stage adds ACL methods and marks the socket session authenticated. Broadcasts are only sent to sockets with `authenticated = True`.
- The server encodes websocket payloads with jsonpickle and manually sends event packets to each authenticated socket.

## Templates And Static UI

- Templates are Jinja files under `ad2web/templates`.
- Layout and forms use Bootstrap, Flask-WTF, macros, and flash messages.
- Keypad UI has separate ADEMCO and DSC templates plus legacy variants:
  - ADEMCO: `templates/keypad/index.html` with `templates/js/keypad/ademco_keypad.js`.
  - DSC: `templates/keypad/dsc.html` with `templates/js/keypad/dsc_keypad.js`.
- Keypad visual behavior:
  - Shows two 16-character LCD-like lines from panel message text.
  - Indicates armed, ready, and chime state with image LEDs/icons.
  - Plays 1-7 beep WAV files unless muted in localStorage.
  - Flashes the display on beeps.
  - Supports mouse, touch, and keyboard input.
  - Confirms emergency/special/custom button presses before sending.
  - Supports user-defined custom buttons and configurable special buttons.
- Static assets include Bootstrap 2/3 copies, jQuery, jQuery UI, DataTables, socket.io.js, Swagger UI, keypad image sprites, sounds, and camera/keypad CSS.
- The UI is tightly coupled to server-rendered globals, old JavaScript libraries, images, and jQuery event wiring.

## Database Models And Schema

- `settings`: key/value table with `name`, `int_value`, and `string_value`.
- `users`: username, email, OpenID, activation key, created time, avatar, password hash, role code, status code, user detail FK, followers/following text fields.
- `user_details`: profile-like fields such as age, phone, URL, location, bio, sex code.
- `user_history`: login IP/time/user-agent records.
- `failed_login_attempts`: failed login name/IP/time/user-agent records.
- `apikeys`: one API key per user.
- `zones`: panel zone ID, name, description.
- `buttons`: user custom keypad buttons with label and code.
- `notifications`: notification description, type, user, enabled flag.
- `notification_settings`: per-notification name/value rows.
- `notification_messages`: event message templates by event ID.
- `event_log`: event type, timestamp, message.
- `cameras`: name, username, password, JPEG URL, user ID.
- `certificates`: certificate/key PEM text, serial/status/type, created/revoked timestamps, description, user ID, CA ID.

## Auth And User Management

- Flask-Login handles browser sessions.
- Username or email plus password login is supported. Passwords use Werkzeug password hashing.
- Login history and failed login attempts are recorded.
- Admin users have `role_code == ADMIN`; admin-only decorators gate settings, API key management, users, certificates, host controls, exports, updater, and similar features.
- First-run setup creates the initial active admin account.
- Password reset emails use a UUID activation key stored on the user row.
- OpenID support exists in forms/models but the route handlers are commented out.
- API authentication uses a generated API key in either the `Authorization` header or `apikey` query parameter. Admin-only API actions check the user associated with that key.

## Notifications

- The notification system always includes a log notifier that writes all events to `event_log`.
- User-configured notification types include Email, Pushover, Twilio SMS, Prowl, Growl, custom HTTP, TwiML, Matrix.org, and UPnP push.
- Notifications subscribe to selected event types. Zone fault/restore/bypass notifications can be filtered by zone.
- Notification settings include time window restrictions, optional delay, and suppression of short-lived zone fault spam.
- Messages are built from editable templates in `notification_messages`, with replacers for zone names, arm type, LRR, RFX, EXP, and AUI fields.
- Notification IO may run through `concurrent.futures.ThreadPoolExecutor` with a configurable worker count.
- UPnP event subscription is exposed through `SUBSCRIBE`/`UNSUBSCRIBE /api/v1/alarmdecoder/event`.

## Configuration

- Flask defaults live in `ad2web/config.py`; production overrides are loaded from instance `production.cfg`.
- Most appliance settings live in the `settings` table, including setup stage, device type/location/path/address/port/SSL, panel config, email, exports, update checker, UPnP port forwarding, special keypad buttons, and secret key.
- Instance root is hard-coded to `/opt/alarmdecoder-webapp/instance`.
- The application creates log and upload folders under the instance root.
- `/opt/alarmdecoder` is inserted into `sys.path` to load the AlarmDecoder Python API from a neighboring checkout.
- `AD_LISTENER_PORT` controls the Socket.IO bind port and API Swagger host default; otherwise port `5000` is used.

## Deployment Assumptions

- Target OS was Raspbian 9-era Raspberry Pi with Python 2.7.
- Assumes packages such as nginx, gunicorn, sendmail, sqlite3, miniupnpc, OpenCV/Python bindings, serial access libraries, and build toolchains.
- Assumes writable `/opt/alarmdecoder`, `/opt/alarmdecoder-webapp`, `/etc/ser2sock`, sometimes `/etc/hosts`, `/etc/hostname`, and `/etc/network/interfaces`.
- Assumes the service user is commonly `pi` in group `dialout`; one included systemd service runs as root.
- Assumes nginx handles HTTPS with a self-signed certificate and proxies to gunicorn/socketio on localhost port 5000.
- Assumes optional ser2sock service for turning a local serial AlarmDecoder into a network socket, including TLS client/server certificate generation.
- Assumes Avahi/mDNS advertising and optional UPnP router port forwarding.

## Python 2 Dependencies

Important dependencies include:

- Flask, Flask-SQLAlchemy, Flask-WTF, Flask-Script, Flask-Babel, Flask-Testing, Flask-Mail, Flask-Login, Flask-OpenID.
- SQLAlchemy, Alembic, Mako.
- gevent 1.1 beta, gevent-socketio, gevent-websocket.
- alarmdecoder Python package.
- pyOpenSSL, cryptography, cffi.
- jsonpickle.
- psutil and sh for host/process/service commands.
- netifaces and miniupnpc for host/network/UPnP operations.
- sleekxmpp, chump, twilio, gntp for notification providers.
- numpy and OpenCV for camera support.
- futures backport for Python 2.7.

## Security Concerns

- Python 2.7, old Flask/gevent-socketio/OpenID/cryptography ecosystem, and bundled old frontend libraries are end-of-life or high-risk.
- Default `SECRET_KEY` is hard-coded as `secret key` until replaced by a database-generated key.
- Several sensitive values are stored in the SQLite database as plaintext or reversible PEM/text: SMTP credentials, camera credentials, notification provider tokens, API keys, certificate private keys.
- API keys are short base32 strings generated from 7 random bytes and can be passed in query strings, which may leak through logs, browser history, or referrers.
- Cross-origin API decorator uses `Access-Control-Allow-Origin: *`.
- Host-level admin routes can reboot/shutdown, edit network files, change hostname, pull git branches, alter ser2sock config, manage certificates, import backups, and expose port forwarding.
- Some deployment examples run gunicorn as root.
- TLS configuration in nginx allows obsolete TLSv1/TLSv1.1 and old ciphers.
- Backup import extracts and trusts tar members by known filenames after reading archive content; it deletes model rows before importing replacements.
- Certificate export and ser2sock config write to `/etc/ser2sock`; permissions must be tightly controlled.
- Websocket authorization relies on Flask session extraction in an old Socket.IO stack and treats incomplete setup as sufficient for some socket methods.
- The notification subscriber removal code appears to reference a misspelled variable (`subuudi`), likely breaking unsubscribe behavior.
- No obvious CSRF protection is visible on many GET routes that perform state-changing operations, such as key generation/disable, delete/remove links, reboot/shutdown, and some updater/admin actions.
