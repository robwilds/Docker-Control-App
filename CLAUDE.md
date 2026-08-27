# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Docker Control App** — A host-side Flask web application that provides a web UI for managing Docker Compose services. It reads the project's `docker-compose.yaml` and exposes a REST API and SPA interface for controlling containers.

## Architecture

```
├── docker-compose.yaml           # Project definition (2 services: web, dozzle)
├── dockercontrolapp/             # Host-side Flask control app
│   ├── app.py                    # Flask server (port 9500), Docker command executor
│   ├── requirements.txt          # Flask + PyYAML
│   └── templates/index.html      # Single-page UI (vanilla JS + CSS)
├── angular/                      # Angular build context for the 'web' service
├── start.sh / start.bat          # Launchers (auto-install deps, open browser)
└── docker-compose.yaml          # Defines 2 services:
    └── web (port 4200, build from angular/)
    └── dozzle (port 8888, image: amir20/dozzle:latest)
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

## Commands

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
docker compose restart             # Same as 'up --restart'
```

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

## Key Implementation Details

### `dockercontrolapp/app.py`

- **Port:** 9500 (hardcoded in `if __name__ == '__main__'`)
- **Volume mounts:** `./angular:/project` and `/project/node_modules` — ensure these paths exist on your host before starting the web service, or the container will fail to start.
- **Logs API:** GET `/api/services/<name>/logs?lines=N`, strips color with `--no-color` flag.
- **Service status:** Uses `docker compose ps --format=json` to parse container states.
- **Docker checks:** `docker info` to verify Docker is running before performing operations.

### `dockercontrolapp/templates/index.html`

- Single HTML file with embedded CSS/JS (no external dependencies).
- Dark mode by default, with a toggle button that saves preference to `localStorage`.
- Polls `/api/services` every 5 seconds to update status badges.
- Log panel auto-refreshes every 5 seconds when open.
- The `web` service is accessed via `http://localhost:4200` (served from the Docker container).

### `dockercontrolapp/templates/index.html` — JS functions

| Function | Purpose |
|----------|---------|
| `checkDockerAndStart()` | Calls `/api/ensure-docker-running`, then `/api/start-all` |
| `fetchServices()` | Calls `/api/services` and calls `renderServices()` |
| `renderServices(services)` | Renders the services grid, determines status class |
| `toggleLog(name)` | Opens/closes log panel; starts/stops auto-refresh interval |
| `fetchLogs(name)` | Fetches last 50 lines of logs for a container |
| `action(cmd, service)` | Dispatches POST to `/api/{cmd}` or `/api/services/{service}/{cmd}` |
| `showToast(msg, type)` | Shows a toast notification at top-right |
| `pollStatus()` | Called every 5s, re-fetches `/api/services` and updates DOM |
| `initTheme()` | Restores theme from `localStorage` on page load |

## Volume Mount Warning

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

## Testing & Quality

No test, lint, typecheck, or CI infrastructure in this repo. Treat as demo/validation tool only.

**Do not run linters/formatting tests** — they don't exist and aren't expected.

## Common Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| "No such file or directory" on container start | Volume mount path doesn't exist on host | Ensure `./angular` and `/project/node_modules` exist |
| Docker Desktop won't start | Not installed on macOS | Install Docker Desktop from https://desktop.docker.com |
| "Docker not found" error | Docker is not running | Start Docker Desktop and wait ~60s |
| Logs show nothing | Container hasn't written logs yet | Wait a moment after starting the container |

## File Structure

```
.
├── docker-compose.yaml
├── dockercontrolapp/
│   ├── app.py
│   ├── requirements.txt
│   └── templates/
│       └── index.html
├── angular/          # Build context for the 'web' service
├── start.sh
└── start.bat
```
