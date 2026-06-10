# Developer Setup Guide

Step-by-step guide for installing, running, and debugging the AlarmDecoder webapp on a **Raspberry Pi running Raspberry Pi OS Trixie (Debian 13)** using VS Code.

## Prerequisites

- Raspberry Pi with **Raspberry Pi OS Trixie** already configured via [Raspberry Pi Imager](https://www.raspberrypi.com/software/) (hostname, user account, SSH, and Wi-Fi set up through the imager's advanced settings)
- SSH access to the Pi from your development machine
- [VS Code](https://code.visualstudio.com/) installed on your development machine

---

## 1 — Connect VS Code to the Raspberry Pi (Remote-SSH)

The recommended workflow is to run VS Code on your laptop or desktop and connect to the Pi over SSH. This gives you the full IDE experience (IntelliSense, integrated terminal, debugger) without needing a desktop environment on the Pi.

### Install the Remote - SSH extension

Open VS Code, go to the **Extensions** panel (`Ctrl+Shift+X`), and install:

- **Remote - SSH** (`ms-vscode-remote.remote-ssh`)

### Configure the SSH connection

Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) → **Remote-SSH: Open SSH Configuration File** → select your user config (e.g. `~/.ssh/config`). Add:

```
Host alarmdecoder
    HostName <pi-ip-or-hostname>.local
    User pi
```

Replace `<pi-ip-or-hostname>` with your Pi's IP address or the hostname you set in Raspberry Pi Imager (e.g. `alarmdecoder`).

### Connect

Command Palette → **Remote-SSH: Connect to Host…** → `alarmdecoder`.

VS Code installs its server component on the Pi automatically (first connection takes a minute). Once connected, the status bar at the bottom left shows `SSH: alarmdecoder`.

---

## 2 — Install system packages on the Pi

Open the integrated terminal in VS Code (`Ctrl+`` ` ``). All commands below run on the Pi.

```bash
sudo apt-get update && sudo apt-get install -y \
  build-essential \
  git \
  libffi-dev \
  libssl-dev \
  python3 \
  python3-dev \
  python3-pip \
  python3-venv \
  sqlite3
```

---

## 3 — Clone the repositories

```bash
sudo mkdir -p /opt/alarmdecoder /opt/alarmdecoder-webapp
sudo chown $USER:$USER /opt/alarmdecoder /opt/alarmdecoder-webapp

cd /opt
git clone https://github.com/nutechsoftware/alarmdecoder.git
git clone https://github.com/nutechsoftware/alarmdecoder-webapp.git
```

---

## 4 — Create a virtual environment and install dependencies

Raspberry Pi OS Trixie enforces [PEP 668](https://peps.python.org/pep-0668/) — `pip` will refuse to install packages into the system Python. Always use a virtual environment.

```bash
cd /opt/alarmdecoder-webapp
python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip setuptools
pip install -r requirements.txt
pip install -e /opt/alarmdecoder   # AlarmDecoder Python library (editable)
```

---

## 5 — Create the instance directory and initialise the database

```bash
sudo mkdir -p /opt/alarmdecoder-webapp/instance/logs
sudo chown -R $USER:$USER /opt/alarmdecoder-webapp/instance

cd /opt/alarmdecoder-webapp
source .venv/bin/activate
python3 manage.py initdb
```

---

## 6 — Open the project folder in VS Code

In VS Code (connected via Remote-SSH):

**File → Open Folder…** → `/opt/alarmdecoder-webapp` → **OK**

### Install recommended extensions (on the remote)

When prompted to install workspace-recommended extensions, click **Install All**. Or install them manually:

- **Python** (`ms-python.python`) — required for debugging
- **Pylance** (`ms-python.vscode-pylance`) — optional, for IntelliSense and type checking

### Select the Python interpreter

1. Command Palette → **Python: Select Interpreter**
2. Choose the venv interpreter: `/opt/alarmdecoder-webapp/.venv/bin/python`

The status bar at the bottom will update to show the selected interpreter.

---

## 7 — Configure the VS Code debugger

Create the directory and file `.vscode/launch.json` in the project root with the following content:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "AlarmDecoder Webapp",
            "type": "debugpy",
            "request": "launch",
            "module": "manage",
            "args": ["run", "--no-reload"],
            "cwd": "${workspaceFolder}",
            "python": "${workspaceFolder}/.venv/bin/python",
            "env": {
                "FLASK_ENV": "development",
                "AD_LISTENER_PORT": "5000"
            },
            "justMyCode": false
        }
    ]
}
```

> **`--no-reload`** disables Flask's auto-reloader. The reloader forks a child process that the VS Code debugger cannot attach to, so breakpoints won't be hit without this flag. To get auto-reload while debugging, use the **Run Without Debugging** mode (`Ctrl+F5`) and restart manually after code changes.
>
> **`justMyCode: false`** lets you step into Flask and library internals. Set it to `true` if you only want to step through application code.

---

## 8 — Run and debug

### Start with the debugger

Press **F5** (or **Run → Start Debugging**). The integrated terminal shows:

```
 * Running on http://0.0.0.0:5000
```

### Access the UI

VS Code Remote-SSH **automatically port-forwards** port 5000, so open `http://localhost:5000` in your local browser.

If the Ports panel doesn't pick it up automatically:

1. View → **Ports** (or the **Ports** tab in the bottom panel)
2. Click **Forward a Port** → enter `5000`

### Set breakpoints

Click in the left gutter (to the left of a line number) in any `.py` file to set a breakpoint. The debugger pauses execution there and you can inspect variables, step through code, and evaluate expressions in the **Debug Console**.

### Stop the server

Click the red **Stop** button in the debug toolbar, or press `Shift+F5`.

---

## 9 — Running without the debugger

For faster iteration (with auto-reload) use the integrated terminal:

```bash
source .venv/bin/activate
python3 manage.py run
```

The server restarts automatically whenever you save a `.py` file.

---

## 10 — Skip the setup wizard (optional)

On first load the browser redirects through the AlarmDecoder setup wizard. To bypass it for faster UI testing, run the following snippet once after `initdb`:

```bash
cd /opt/alarmdecoder-webapp
source .venv/bin/activate
python3 - <<'EOF'
from ad2web import create_app
from ad2web.extensions import db
from ad2web.setup.models import Setting
from ad2web.setup.constants import SETUP_COMPLETE

app, _ = create_app()
with app.app_context():
    s = Setting.get_by_name('setup_stage')
    if s:
        s.value = SETUP_COMPLETE
    else:
        db.session.add(Setting(name='setup_stage', value=SETUP_COMPLETE))
    db.session.commit()
    print("Setup wizard bypassed.")
EOF
```

---

## 11 — Running the test suite

```bash
cd /opt/alarmdecoder-webapp
source .venv/bin/activate
python3 -m pytest tests/ -v
```

---

## 12 — Log files

Application logs are written to `/opt/alarmdecoder-webapp/instance/logs/`. Tail them in the VS Code terminal:

```bash
tail -f /opt/alarmdecoder-webapp/instance/logs/*.log
```

Flask request logs and debug output also appear in the integrated terminal where the server was launched.

---

## 13 — Reset the database

To start fresh with a clean database:

```bash
cd /opt/alarmdecoder-webapp
source .venv/bin/activate
python3 manage.py initdb
```

> **Warning:** This drops all tables and re-creates them. All settings, user accounts, and notification configuration will be lost.

---

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `externally-managed-environment` error from pip | PEP 668: Trixie blocks pip outside a venv | Always `source .venv/bin/activate` first |
| Breakpoints not hit | Flask reloader forks a child process | Use `--no-reload` in `launch.json` args (already set above) |
| `OSError: [Errno 98] Address already in use` | Port 5000 already in use | Run `sudo lsof -i :5000` to find the PID and `kill <PID>` |
| AlarmDecoder not connecting | No device attached or ser2sock not running | The app starts fine without a device — skip the setup wizard or check serial port settings |
| WebSocket disconnects in browser | Proxied through nginx without WS headers | Use `manage.py run` directly during development (no nginx proxy) |
| VS Code "Python extension not found" | Extension installed locally, not on remote | In VS Code with Remote-SSH connected, install the Python extension on the **remote** (SSH) side |
