# Docker Control App

A host-side Flask web application that provides a web UI for managing Docker Compose services. It reads the project's `docker-compose.yaml` and exposes a REST API and SPA interface for controlling containers.

## Features

- **Service list** with live **status badges** (running/stopped/unknown) — polls every 5 seconds
- **Start All**, **Stop All** (persists containers via `docker compose stop`), **Restart All**
- **Per-service Start / Stop** buttons
- **Per-service log panel** — slides open, tails last 50 lines, auto-refreshes every 5 seconds
- **Dark mode** toggle with persistent theme preference (saved to `localStorage`)

## Prerequisites

- [Python 3](https://python.org) installed on your system
- [Docker](https://docker.com) and [Docker Compose](https://docs.docker.com/compose/) installed
- The `docker-compose.yaml` file at the project root

## Quick start

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

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/services` | GET | List all services from `docker-compose.yaml` with their current status |
| `/api/start-docker-desktop` | POST | Attempt to open/start Docker Desktop (macOS only) |
| `/api/ensure-docker-running` | POST | Check if Docker is running; if not, start Docker Desktop and wait up to 60s |
| `/api/start-all` | POST | Start all containers (`docker compose up -d`) |
| `/api/stop-all` | POST | Stop all containers (`docker compose stop`) |
| `/api/restart-all` | POST | Restart all containers (`docker compose restart`) |
| `/api/services/<name>/start` | POST | Start a specific service (`docker compose up -d <name>`) |
| `/api/services/<name>/stop` | POST | Stop a specific service (`docker compose stop <name>`) |
| `/api/services/<name>/logs` | GET | Fetch logs for a container (GET `/api/services/{name}/logs?lines=N`) |

## Docker Compose Operations

```bash
# Start controller (installs deps and opens browser)
./start.sh              # macOS/Linux
start.bat               # Windows

# Manual start
pip install -r dockercontrolapp/requirements.txt
python dockercontrolapp/app.py

# Docker Compose operations
docker compose up --build          # or 'docker compose up -d'
docker compose stop                # v2: 'docker compose stop', NOT 'up -d --no-start'
docker compose restart             # Same as 'docker compose restart'
```

## Architecture

```
├── docker-compose.yaml           # Project definition (2 services: web, dozzle)
├── dockercontrolapp/             # Host-side Flask control app
│   ├── app.py                    # Flask server (port 9500), Docker command executor
│   ├── requirements.txt          # Flask + PyYAML
│   └── templates/index.html      # Single-page UI (vanilla JS + CSS)
├── angular/                      # Angular build context for the 'web' service
└── start.sh / start.bat          # Launchers
```

**Key points:**
- The Flask app runs **on the host** (not inside Docker).
- It reads `docker-compose.yaml` from the project root.
- It executes `docker compose v2` commands via subprocess.
- The Angular app is built into a Docker container (port 4200) and served as a web service.

## Services

From `docker-compose.yaml`:

| Service | Type | Port | Build From |
|---------|-------|-------|-------------|
| `web` | Angular SPA | 4200 | `angular/` dir with build target `builder` |
| `dozzle` | Log viewer | 8888 | Docker image: `amir20/dozzle:latest` |

## Key Implementation Details

### `dockercontrolapp/app.py`

- **Port:** 9500 (hardcoded in `if __name__ == '__main__'`)
- **Logs API:** GET `/api/services/<name>/logs?lines=N`, strips color with `--no-color` flag.
- **Service status:** Uses `docker compose ps --format=json` to parse container states.
- **Docker checks:** `docker info` to verify Docker is running before performing operations.

### `dockercontrolapp/templates/index.html`

- Single HTML file with embedded CSS/JS (no external dependencies).
- Polls `/api/services` every 5 seconds to update status badges.
- Log panel auto-refreshes every 5 seconds when open.
- The `web` service is accessed via `http://localhost:4200` (served from the Docker container).

## ⚠️ Volume Mount Warning

The `web` service mounts `./angular:/project` and `/project/node_modules`. On macOS, the path `./angular` may resolve to `/Users/robertwilds/Downloads/git/Docker Control App/angular`, but the Docker container won't see the `angular` directory unless the **parent** directory (`git/Docker Control App`) is also mounted.

**Fix:** Add this to `docker-compose.yaml`:

```yaml
volumes:
  - ./angular:/project
  - /project/node_modules
  - ../..:/project  # Mount the repo root so 'angular' is visible inside the container
```

Or explicitly mount the parent:

```yaml
volumes:
  - ../../angular:/project
  - /project/node_modules
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-------|
| "No such file or directory" on container start | Volume mount path doesn't exist on host | Ensure `./angular` and `/project/node_modules` exist |
| Docker Desktop won't start | Not installed on macOS | Install Docker Desktop from https://desktop.docker.com |
| "Docker not found" error | Docker is not running | Start Docker Desktop and wait ~60s |
| Logs show nothing | Container hasn't written logs yet | Wait a moment after starting the container |

## Screenshot

![screenshot](https://github.com/user-attachments/assets/f2e783c2-9d70-437d-8c61-0828e77149d7)

---

> **Note:** This project is a demo/validation tool. There is no test, lint, typecheck, or CI infrastructure.
