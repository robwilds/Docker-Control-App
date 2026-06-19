## Docker Control App

Web UI to manage Docker Compose services — lists services, shows live status (auto-refreshes every 5 seconds), start/stop/restart, and per-container log tailing. Works with any `docker-compose.yaml` at the project root.

### Features

- Service list with live **status badges** (running/stopped/unknown) — polls every 5 seconds
- **Start All**, **Stop All** (persists containers via `docker compose stop`), **Restart All**
- **Per-service Start / Stop** buttons
- **Per-service log panel** — slides open, tails last 50 lines, auto-refreshes every 5 seconds

### Prerequisites

- [Python 3](https://python.org) installed on your system
- [Docker](https://docker.com) and [Docker Compose](https://docs.docker.com/compose/) installed
- The `docker-compose.yaml` file at the project root

### Quick start

**Option A — helper scripts (auto-installs dependencies, opens browser):**

- **macOS / Linux:** `./start.sh`
- **Windows:** `start.bat`

**Option B — manual:**

```bash
pip install -r dockercontrolapp/requirements.txt
python dockercontrolapp/app.py
```

> On some systems you may need `pip3` instead of `pip` and `python3` instead of `python` — the helper scripts handle this automatically.

Open [http://localhost:9500](http://localhost:9500) in your browser.

<img width="1176" height="750" alt="image" src="https://github.com/user-attachments/assets/f2e783c2-9d70-437d-8c61-0828e77149d7" />
