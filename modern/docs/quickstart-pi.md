# Raspberry Pi Quick-Start Guide

A step-by-step guide to deploying AlarmDecoder Modern on a Raspberry Pi from scratch.

---

## Hardware Requirements

| Board | Status | Notes |
|---|---|---|
| **Pi 4 / Pi 5** | ✅ Recommended | Full feature support; on-device npm build is fast |
| **Pi Zero 2W** | ✅ Functional | Slower; recommend using a pre-built release archive from GitHub Releases to avoid the npm build step |
| **Pi 3B / Pi 3B+** | ✅ Functional | Works fine; on-device npm build may take several minutes |
| **Pi 2** | ⚠️ Marginal | Works but slow; use a pre-built release archive |
| **Pi Zero 1 (original)** | ⛔ On-device build unsupported | Requires a pre-built release archive from GitHub Releases; on-device `npm run build` will OOM |

> [!TIP]
> For any Pi with less than 1 GB RAM, always download the pre-built `.tar.gz` archive from [GitHub Releases](https://github.com/nutechsoftware/alarmdecoder-webapp/releases) rather than building on-device. The install script will automatically skip the npm build if `frontend/dist` is already present in the archive.

---

## 1. Prepare the Operating System

**Recommended OS:** Raspberry Pi OS Lite 64-bit (Debian Bookworm).

Flash the image with [Raspberry Pi Imager](https://www.raspberrypi.com/software/), enable SSH in the imager's advanced settings, then boot and SSH in.

Update the system:

```bash
sudo apt-get update && sudo apt-get upgrade -y
```

---

## 2. Install System Dependencies

Install the base packages needed to run and (optionally) build AlarmDecoder Modern:

```bash
sudo apt-get install -y git python3 python3-venv python3-pip
```

### Optional: Install Node.js for On-Device Frontend Build

> [!NOTE]
> Skip this step if you are deploying from a pre-built release archive (the `frontend/dist` directory will already be included and the npm build will be skipped automatically).

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

Verify the installation:

```bash
node --version   # should print v20.x.x
npm --version
```

---

## 3. Get the Application

### Option A — Clone the Repository (on-device build)

```bash
git clone https://github.com/nutechsoftware/alarmdecoder-webapp.git
cd alarmdecoder-webapp/modern
```

### Option B — Download a Pre-Built Release Archive (recommended for low-RAM Pis)

1. Go to [GitHub Releases](https://github.com/nutechsoftware/alarmdecoder-webapp/releases) and copy the URL for the latest `alarmdecoder-modern-vX.Y.Z.tar.gz`.

2. Download and extract on the Pi:

```bash
wget https://github.com/nutechsoftware/alarmdecoder-webapp/releases/download/vX.Y.Z/alarmdecoder-modern-vX.Y.Z.tar.gz
tar -xzf alarmdecoder-modern-vX.Y.Z.tar.gz
cd modern
```

---

## 4. Run the Installer

The installer must be run as root from inside the `modern/` directory:

```bash
sudo bash deploy/install.sh
```

The script will:
- Create the `alarmdecoder-modern` system user and add it to the `dialout` group
- Copy application files to `/opt/alarmdecoder-modern`
- Create a Python virtual environment and install backend dependencies
- Run database migrations (Alembic)
- Build the frontend (or skip if `frontend/dist` is already present)
- Install and enable the systemd service
- Prompt you to create an admin user

---

## 5. Configure the Environment

The installer copies the example config to `/etc/alarmdecoder-modern/alarmdecoder-modern.env`. Edit it now:

```bash
sudo nano /etc/alarmdecoder-modern/alarmdecoder-modern.env
```

### Generate a Strong Session Secret

> [!IMPORTANT]
> You **must** replace `ALARMDECODER_SESSION_SECRET` with a strong random value before starting the service. Rotating this value later will invalidate all active sessions and any encrypted panel PIN stored in the database.

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the output into the `ALARMDECODER_SESSION_SECRET=` line in the env file.

### Key Variables to Review

| Variable | Default | Description |
|---|---|---|
| `ALARMDECODER_ADAPTER` | `ser2sock` | Connection type: `ser2sock`, `serial`, `ad2usb`, `ad2pi`, `fake` |
| `ALARMDECODER_SER2SOCK_HOST` | `alarmdecoder.local` | Hostname/IP of ser2sock server |
| `ALARMDECODER_SERIAL_PATH` | `/dev/ttyUSB0` | Serial device path (for local adapters) |
| `ALARMDECODER_READ_ONLY` | `true` | Disables all panel commands — start here! |
| `ALARMDECODER_SESSION_SECRET` | *(placeholder)* | **Must be changed** |

---

## 6. Start the Service

```bash
sudo systemctl start alarmdecoder-modern
sudo systemctl status alarmdecoder-modern
```

Verify the API is responding:

```bash
curl http://localhost:8000/health
```

You should see a JSON response like `{"status": "ok"}`.

---

## 7. Access the Web UI

Open a browser and navigate to:

```
http://<your-pi-hostname-or-ip>:8000
```

Log in with the admin account you created during installation. If you skipped that step, you can create one now:

```bash
sudo /opt/alarmdecoder-modern/backend/.venv/bin/python -m app.cli create-admin
```

---

## 8. Optional: Reverse Proxy with nginx

For HTTPS or to expose the app on port 80/443, use nginx as a reverse proxy. An example config is provided:

```bash
sudo apt-get install -y nginx
sudo cp /opt/alarmdecoder-modern/deploy/nginx.conf.example /etc/nginx/sites-available/alarmdecoder-modern
sudo ln -s /etc/nginx/sites-available/alarmdecoder-modern /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Update `ALARMDECODER_CORS_ORIGINS` in the env file to include your nginx origin if accessing the API from a different domain.

---

## Hardware-Specific Notes

### Pi 4 / Pi 5
Full feature support. On-device `npm run build` is fast (under 2 minutes). No special steps needed.

### Pi Zero 2W
Functional but notably slower. The npm build will complete but may take 10–20 minutes and push RAM usage high. **Strongly recommended: use a pre-built release archive from GitHub Releases** so that the install script skips the npm build step entirely.

### Pi Zero 1 (original)
On-device `npm run build` will run out of memory and fail. **You must use a pre-built release archive.** Download the `.tar.gz` from GitHub Releases (which includes the pre-built `frontend/dist`), and the install script will skip the build step automatically.

### Serial Device Access (AD2USB / AD2PI / AD2Serial)

The install script adds the `alarmdecoder-modern` service user to the `dialout` group automatically. Verify it:

```bash
groups alarmdecoder-modern
# should include: dialout
```

If the device is still not accessible after restarting the service, check the device path:

```bash
ls -la /dev/ttyUSB* /dev/ttyAMA* 2>/dev/null
```

---

## 9. First Steps After Install

> [!IMPORTANT]
> Always validate your hardware connection in read-only mode before enabling command sending.

1. **Keep `ALARMDECODER_READ_ONLY=true`** (the default). Restart the service and confirm the panel status is displayed correctly in the UI.
2. **Validate hardware**: arm/disarm your panel physically and confirm events appear in the dashboard.
3. **Enable commands only when ready**: set `ALARMDECODER_READ_ONLY=false` and `ALARMDECODER_ALLOW_COMMANDS=true`, then restart the service.

---

## 10. Backup

Back up the SQLite database (contains users, settings, and event history):

```bash
sqlite3 /var/lib/alarmdecoder-modern/alarmdecoder-modern.db ".backup /home/pi/alarmdecoder-backup-$(date +%Y%m%d).db"
```

To restore:

```bash
sudo systemctl stop alarmdecoder-modern
sudo cp /home/pi/alarmdecoder-backup-YYYYMMDD.db /var/lib/alarmdecoder-modern/alarmdecoder-modern.db
sudo chown alarmdecoder-modern:alarmdecoder-modern /var/lib/alarmdecoder-modern/alarmdecoder-modern.db
sudo systemctl start alarmdecoder-modern
```

---

## 11. Troubleshooting

### View Live Logs

```bash
journalctl -u alarmdecoder-modern -f
```

### View Recent Logs

```bash
journalctl -u alarmdecoder-modern --since "1 hour ago"
```

### Common Issues

| Symptom | Likely Cause | Fix |
|---|---|---|
| Service won't start | Bad env variable or missing secret | Check logs; verify `alarmdecoder-modern.env` |
| `Permission denied` on serial device | User not in dialout group | `sudo usermod -aG dialout alarmdecoder-modern && sudo systemctl restart alarmdecoder-modern` |
| Web UI unreachable | Service not running or wrong port | `systemctl status alarmdecoder-modern` and `curl http://localhost:8000/health` |
| `npm: not found` during install | Node.js not installed | Install Node.js 20 (see Step 2) or use a pre-built archive |
| Database migration error | Schema mismatch after update | Check logs; run `sudo -u alarmdecoder-modern /opt/alarmdecoder-modern/backend/.venv/bin/alembic upgrade head` manually |

---

## Updating

To update to a newer version, use the update script which handles brief downtime gracefully:

```bash
cd /path/to/new/alarmdecoder-modern-source
sudo bash deploy/update.sh
```

The update script stops the service, syncs files, runs migrations, rebuilds the frontend (or skips if pre-built), restarts the service, and polls the health endpoint to confirm recovery.
