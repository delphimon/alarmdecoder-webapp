# AlarmDecoder Webapp

## Summary

This is the home of the official webapp for the [AlarmDecoder](http://www.alarmdecoder.com) family of home security devices.

![Keypad Screenshot](http://github.com/nutechsoftware/alarmdecoder-webapp/raw/master/screenshot.png "Keypad Screenshot")

## Features

- Supports all AlarmDecoder devices: AD2USB, AD2SERIAL and AD2PI
- Web-based keypad for your alarm system
- Notifications on alarm events
- Multiple user accounts and per-user notifications and certificates (if configured)

## Requirements

- **Python 3.6+** (Python 2 is no longer supported)
- nginx >= 1.6
- gunicorn
- gevent + gevent-websocket (for WebSocket support)

> Other web/WSGI servers with WebSocket support will likely work but require additional configuration.

## Installation

These instructions assume you have already used the [Raspberry Pi Imager](https://www.raspberrypi.com/software/) to flash **Raspberry Pi OS (Trixie / Debian 13)** and have configured your hostname, user account, SSH, and Wi-Fi through the imager's advanced settings.

> **Developers:** See [DEVELOPMENT.md](DEVELOPMENT.md) for a full guide on setting up a local development environment and debugging with VS Code.

### 1 — Prepare the UART (AD2PI users only)

The GPIO UART must be free for the AlarmDecoder AD2PI. Disable the kernel serial console and enable the UART:

```bash
# Disable serial console
sudo raspi-config nonint do_serial 1

# Enable UART and reassign Bluetooth to the mini-UART
# (Trixie uses /boot/firmware/config.txt)
sudo sed -i '/enable_uart\|pi3-miniuart-bt-overlay\|force_turbo/d' /boot/firmware/config.txt
printf '\nenable_uart=1\ndtoverlay=pi3-miniuart-bt-overlay\nforce_turbo=1\n' \
  | sudo tee -a /boot/firmware/config.txt

sudo reboot
```

> AD2USB and AD2SERIAL users can skip this step.

### 2 — Install system packages

```bash
sudo apt-get update && sudo apt-get install -y \
  autoconf \
  automake \
  build-essential \
  cmake \
  git \
  libcurl4-openssl-dev \
  libffi-dev \
  libssl-dev \
  minicom \
  nginx \
  python3 \
  python3-dev \
  python3-pip \
  python3-venv \
  screen \
  sendmail \
  sqlite3 \
  zlib1g-dev
```

### 3 — Create application directories

```bash
sudo mkdir -p /opt/alarmdecoder /opt/alarmdecoder-webapp
sudo chown pi:pi /opt/alarmdecoder /opt/alarmdecoder-webapp
```

### 4 — Clone the repositories

```bash
cd /opt
git clone https://github.com/nutechsoftware/alarmdecoder.git
git clone https://github.com/nutechsoftware/alarmdecoder-webapp.git
```

### 5 — Create a Python virtual environment and install dependencies

Raspberry Pi OS Trixie enforces [PEP 668](https://peps.python.org/pep-0668/) and prevents `pip` from installing packages into the system Python. Use a virtual environment:

```bash
cd /opt/alarmdecoder-webapp
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools
pip install -r requirements.txt
pip install -e /opt/alarmdecoder   # install the AlarmDecoder Python library
pip install gunicorn               # install gunicorn inside the venv
```

### 6 — Set up ser2sock (serial/network bridge)

```bash
cd /opt
git clone https://github.com/nutechsoftware/ser2sock.git
cd /opt/ser2sock && ./configure && make && sudo cp ser2sock /usr/local/bin/

# Create config directory and deploy default config
sudo mkdir -p /etc/ser2sock
sudo cp /opt/ser2sock/etc/ser2sock/ser2sock.conf /etc/ser2sock/
sudo chown -R pi:pi /etc/ser2sock

# Enable raw device mode and set the correct serial device
sudo sed -i 's/raw_device_mode = 0/raw_device_mode = 1/' /etc/ser2sock/ser2sock.conf
sudo sed -i 's|device = /dev/ttyAMA0|device = /dev/serial0|' /etc/ser2sock/ser2sock.conf

# Install and enable the ser2sock init script
sudo cp /opt/ser2sock/init/ser2sock /etc/init.d/
sudo sed -i 's/EXTRA_START_ARGS=/#EXTRA_START_ARGS=/' /etc/init.d/ser2sock
sudo sed -i 's/#RUN_AS=.*/RUN_AS=pi:pi/' /etc/init.d/ser2sock
sudo update-rc.d ser2sock defaults
```

Grant the `pi` user access to serial ports and allow the webapp to update network configuration files:

```bash
sudo usermod -a -G dialout pi
sudo chgrp dialout /etc/hosts /etc/hostname
sudo chmod g+w /etc/hosts /etc/hostname
```

### 7 — Configure nginx

```bash
# Generate a self-signed TLS certificate
sudo mkdir -p /etc/nginx/ssl
sudo openssl req \
  -x509 -nodes -sha256 -days 3650 -newkey rsa:4096 \
  -keyout /etc/nginx/ssl/alarmdecoder.key \
  -out /etc/nginx/ssl/alarmdecoder.crt \
  -subj '/CN=AlarmDecoder.local/O=AlarmDecoder.com/C=US'

# Install the AlarmDecoder site and enable it
sudo rm -f /etc/nginx/sites-enabled/default
sudo cp /opt/alarmdecoder-webapp/contrib/nginx/alarmdecoder /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/alarmdecoder /etc/nginx/sites-enabled/alarmdecoder

sudo systemctl enable nginx
```

### 8 — Configure the gunicorn systemd service

The service file in `contrib/gunicorn.d/alarmdecoder.service` is configured to run gunicorn from the virtual environment. Copy it into place:

```bash
sudo cp /opt/alarmdecoder-webapp/contrib/gunicorn.d/alarmdecoder.service \
        /etc/systemd/system/alarmdecoder.service
sudo systemctl daemon-reload
sudo systemctl enable alarmdecoder
```

> If you placed the virtual environment somewhere other than `/opt/alarmdecoder-webapp/.venv`, edit the `ExecStart` line in the service file before enabling it.

### 9 — Configure log rotation

```bash
cat <<'EOF' | sudo tee /etc/logrotate.d/alarmdecoder > /dev/null
/opt/alarmdecoder-webapp/instance/logs/*.log {
  weekly
  missingok
  rotate 5
  compress
  delaycompress
  notifempty
  create 0640 pi pi
  sharedscripts
}
EOF
```

### 10 — Enable Avahi mDNS discovery (optional)

This lets other devices on the local network find the Pi by hostname (e.g. `alarmdecoder.local`):

```bash
cat <<'EOF' | sudo tee /etc/avahi/services/alarmdecoder.service
<?xml version="1.0" standalone="no"?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">%h</name>
  <service>
    <type>_device-info._tcp</type>
    <port>0</port>
    <txt-record>model=AlarmDecoder</txt-record>
  </service>
  <service>
    <type>_ssh._tcp</type>
    <port>22</port>
  </service>
</service-group>
EOF
```

### 11 — Initialise the database

```bash
cd /opt/alarmdecoder-webapp
source .venv/bin/activate
python3 manage.py initdb
```

### 12 — Start the services

```bash
sudo systemctl start alarmdecoder
sudo systemctl start nginx
```

The webapp is now accessible at `https://<hostname>.local/` (or the Pi's IP address). The first visit will walk through the setup wizard to configure the AlarmDecoder device connection.

## Python Dependencies

All dependencies are listed in `requirements.txt` and must be installed inside a virtual environment (required on Trixie):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Key dependencies:

- **Flask** >= 2.0 with **Flask-SocketIO** >= 5.0 (replaces the legacy gevent-socketio)
- **gevent** >= 21.12 + **gevent-websocket** >= 0.10 (WebSocket transport for gunicorn)
- **WTForms** >= 3.0, **Flask-Babel** >= 3.0, **Flask-Login** >= 0.6, **Werkzeug** >= 2.0
- **SQLAlchemy** >= 1.4 with **alembic** >= 1.0 for database migrations
- **click** (CLI management via `manage.py`)

## Running the Application

### Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for the full developer setup guide including VS Code debugging.

```bash
source .venv/bin/activate
python3 manage.py run
```

### Production (gunicorn)

```bash
source .venv/bin/activate
gunicorn \
  --worker-class=geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
  --workers=1 --timeout=120 wsgi:application
```

> **Note:** `--workers=1` is required for Socket.IO state consistency. The `GeventWebSocketWorker` class (from `gevent-websocket`) handles WebSocket upgrade requests correctly under gevent.

### Database initialisation

```bash
source .venv/bin/activate
python3 manage.py initdb
```

## Support

Please visit our [forums](http://www.alarmdecoder.com/forums/).

## Contributing

We love the open-source community and welcome any contributions! Just submit a pull request through [GitHub](https://github.com/nutechsoftware/alarmdecoder-webapp).
