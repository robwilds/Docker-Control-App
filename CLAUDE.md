# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Docker Control App** — A Flask web application that provides a web UI for managing Docker Compose services. It reads the project's `docker-compose.yaml` and exposes a REST API and SPA interface for controlling containers. It runs either **in a container** (recommended) or **directly on the host** with Python.

## Architecture

```
├── docker-compose.yaml           # Managed project (2 services: web, dozzle)
├── docker-compose.controller.yaml# Controller's own project (1 service: controller)
├── dockercontrolapp/             # Flask control app
│   ├── app.py                    # Flask server (port 9500), Docker command executor
│   ├── Dockerfile                # python:3.12-slim + docker CLI + compose plugin
│   ├── .dockerignore
│   ├── requirements.txt          # Flask + PyYAML + gunicorn
│   └── templates/index.html      # Single-page UI (vanilla JS + CSS)
├── angular/                      # Angular build context for the 'web' service
└── start.sh / start.bat          # Launchers (docker | local mode picker)
```

**Key points:**
- The Flask app runs **in a container** by default (`./start.sh docker`), or on the host via `./start.sh local`.
- It reads `docker-compose.yaml` from the repo root.
- It executes `docker compose v2` commands via subprocess.
- The Angular app is built into a Docker container (port 4200) and served as a web service.

### Two compose projects, on purpose

| File | Project name | Contents |
|------|--------------|----------|
| `docker-compose.yaml` | `docker-control-app` | `web`, `dozzle` — the managed project |
| `docker-compose.controller.yaml` | `docker-control-app-controller` | `controller` — the UI |

The controller is **not** a service in `docker-compose.yaml`. If it were, its own Stop All / Restart All buttons would stop the container serving those buttons with no way back from the UI. As a result it never lists itself in `/api/services` and is never touched by Stop All / Restart All.

### Why the repo is mounted at its identical host path

`"${REPO_DIR}:${REPO_DIR}"` in `docker-compose.controller.yaml` is deliberate, not a shortcut. The compose CLI resolves relative paths (`build.context: angular`, `./angular:/project`) client-side into absolute paths, then the daemon bind-mounts those absolute paths on the **host**. Mounting the repo at any other path (e.g. `/project`) would make the host try to bind `/project/angular`, which does not exist there. It also keeps the derived project name identical on both sides. `start.sh` exports `REPO_DIR` plus `DOCKER_SOCK` into a gitignored `.env`.

### Why the socket path is derived

Docker Desktop for macOS listens on `~/.docker/run/docker.sock` and does **not** create `/var/run/docker.sock`; mounting that path silently yields an empty directory. `start.sh` resolves it via `docker context inspect "$(docker context show)"`. Both compose files use `${DOCKER_SOCK:-/var/run/docker.sock}` (correct on plain Linux).

### Why the image build context is `dockercontrolapp/`

The controller needs only `app.py`, `requirements.txt` and `templates/`. `context: dockercontrolapp` keeps `angular/` — including `node_modules` — out of the build context, which would otherwise be shipped to the daemon on every rebuild. The Angular app is built by its own `web` service.

### Bootstrap order is a hard constraint

Docker must be running **before** the controller starts. A Linux container cannot launch Docker Desktop, and the controller container cannot exist while the daemon is down. `start.sh` checks this up front. The UI's *Check Docker / Start If Needed* button only works in local mode; in container mode `IN_CONTAINER=1` replaces it with a message pointing the user at Docker Desktop.

## Services

From `docker-compose.yaml`:

| Service | Type | Port | Build From |
|---------|-------|-------|-------------|
| `web` | Angular SPA | 4200 | `angular/` dir with build target `builder` |
| `dozzle` | Log viewer | 8888 | Docker image: `amir20/dozzle:latest` |

`deploy: mode: global` on `dozzle` is a Swarm-only key; `docker compose` ignores it.

## Commands

```bash
# Start controller
./start.sh docker       # container mode (recommended)  | start.bat docker
./start.sh local        # host mode with Python        | start.bat local
./start.sh              # interactive prompt           | start.bat

# Controller management
docker compose -f docker-compose.controller.yaml up -d --build
docker compose -f docker-compose.controller.yaml logs -f controller
docker compose -f docker-compose.controller.yaml down

# Manual host start
pip install -r dockercontrolapp/requirements.txt
python dockercontrolapp/app.py

# Managed project operations
docker compose up --build          # or 'docker compose up -d'
docker compose stop                # v2: 'docker compose stop', NOT 'up -d --no-start'
docker compose restart             # Same as 'up --restart'
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Liveness + Docker reachability; `503` when Docker is down |
| `/api/services` | GET | List all services from `docker-compose.yaml` with their current status (never includes the controller) |
| `/api/start-docker-desktop` | POST | Start Docker Desktop — **host mode only**; explanatory message in container mode |
| `/api/ensure-docker-running` | POST | Check Docker; in host mode also waits up to 60s after launching Docker Desktop |
| `/api/start-all` | POST | Start all containers (`docker compose up -d`) |
| `/api/stop-all` | POST | Stop all containers (`docker compose stop`) |
| `/api/restart-all` | POST | Restart all containers (`docker compose restart`) |
| `/api/services/<name>/start` | POST | Start a specific service (`docker compose up -d <name>`) |
| `/api/services/<name>/stop` | POST | Stop a specific service (`docker compose stop <name>`) |
| `/api/services/<name>/logs` | GET | Fetch logs for a container (add `?lines=N`, default 50) |

## Key Implementation Details

### `dockercontrolapp/app.py`

- **Port:** 9500
- **WSGI:** gunicorn `--bind 0.0.0.0:9500 --threads 4 --timeout 660 app:app`. `--timeout` must exceed `COMPOSE_TIMEOUT` (600s) or the worker dies mid-build; `--threads` keeps 5s polling responsive. Local mode uses Flask's dev server with `debug=True`.
- **Timeouts:** `COMPOSE_READ_TIMEOUT` (60s) for `ps`/`logs`/`config`; `COMPOSE_TIMEOUT` (600s) for everything else, since a cold image build is slow. Env-overridable.
- **Logs API:** GET `/api/services/<name>/logs?lines=N`, strips color with `--no-color` flag.
- **Service status:** Uses `docker compose ps --format=json` to parse container states. Since Compose v2.21 this emits **JSON Lines** (one object per line), which the per-line parser expects.
- **Docker checks:** `docker info` to verify Docker is running before performing operations.
- **Process handling:** compose commands run via `Popen(start_new_session=True)` and are killed **by process group** on timeout. Killing only the direct child deadlocks — `docker compose up` spawns grandchildren holding the stdout/stderr pipes, so `communicate()` blocks forever and the request never returns.
- **Error handling:** every endpoint returns JSON, never an HTML 500, so the frontend's `res.json()` cannot throw. `docker_unreachable_error()` guards Stop All / per-service Stop.
- **Container mode:** `IN_CONTAINER=1` makes the two Docker Desktop endpoints return explanatory messages — a Linux container cannot launch macOS Docker Desktop, and Docker must already be running for the container to exist.
- **`restart: unless-stopped`:** recovers from crashes and Docker daemon restarts, but deliberately does *not* restart a container the user stopped or `docker kill`ed. Verified empirically.

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
| `action(cmd, service)` | Dispatches POST to `/api/<cmd>` or `/api/services/<service>/<cmd>` |
| `showToast(msg, type)` | Shows a toast notification at top-right |
| `pollStatus()` | Called every 5s, re-fetches `/api/services` and updates DOM |
| `initTheme()` | Restores theme from `localStorage` on page load |

## Verification

```bash
curl -s localhost:9500/api/health        # app + Docker reachability
curl -s localhost:9500/api/services      # web + dozzle only, no controller
docker compose ls -a                     # exactly docker-control-app + -controller
```

`/api/health` returning `503` means the app is up but the daemon is unreachable; read `docker_error`. If `/api/services` ever lists `controller`, something has put the controller into the managed project, defeating the separation described above.

`docker compose ls -a` showing a third project whose config path no longer exists is a leftover from a renamed/moved checkout. Clean it with `docker compose -p <name> down --remove-orphans`.

## Testing & Quality

No test, lint, typecheck, or CI infrastructure in this repo. Treat as demo/validation tool only.

**Do not run linters/formatting tests** — they don't exist and aren't expected.

## Common Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| `Docker is not running. Start Docker Desktop and try again.` | Daemon down, so the controller can't be started at all | Start Docker Desktop, then re-run `./start.sh docker` |
| `REPO_DIR must be set to the repo root` | Running compose by hand without `.env` | Run `./start.sh docker` once, or `export REPO_DIR=$(pwd)` |
| Controller won't come up after moving/renaming the repo | `.env` holds stale absolute paths | Re-run `./start.sh docker` to refresh it |
| Controller UI shows every service as stopped | `docker` CLI missing or socket not mounted | Check `curl localhost:9500/api/health`, then rebuild |
| Dozzle shows no containers | Socket path wrong for your Docker install | Ensure `DOCKER_SOCK` is set (see above) |
| `web` service will not start | Repo not mounted at its host path | Confirm `REPO_DIR` is the absolute repo root |
| Duplicate/ghost containers appear | Managed project name mismatch | `docker compose ls -a` should show exactly two projects for this repo |
| A start request never returns | Compose build exceeded the timeout | Raise `COMPOSE_TIMEOUT` and gunicorn `--timeout` together |
| Browser shows "Request failed" instead of a message | Controller container is not running | `docker compose -f docker-compose.controller.yaml logs controller` |
| Logs show nothing | Container hasn't written logs yet | Wait a moment after starting the container |

**Security**: the controller mounts `docker.sock`, which is root-equivalent access to the host. Never suggest exposing port 9500 to an untrusted network.

## File Structure

```
.
├── docker-compose.yaml            # Managed project: web, dozzle
├── docker-compose.controller.yaml # Controller project: controller
├── dockercontrolapp/
│   ├── app.py
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── requirements.txt
│   └── templates/
│       └── index.html
├── angular/          # Build context for the 'web' service
├── .env              # Generated by start.sh (gitignored): REPO_DIR, DOCKER_SOCK
├── start.sh
└── start.bat
```
