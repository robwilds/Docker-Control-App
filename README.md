# Docker Control App

A Flask web application that provides a web UI for managing Docker Compose services. It reads the project's `docker-compose.yaml` and exposes a REST API and SPA interface for controlling containers.

It can run either **inside a container** (recommended) or **directly on the host** with Python.

## Features

- **Service list** with live **status badges** (running/stopped/unknown) — polls every 5 seconds
- **Start All**, **Stop All** (persists containers via `docker compose stop`), **Restart All**
- **Per-service Start / Stop** buttons
- **Per-service log panel** — slides open, tails last 50 lines, auto-refreshes every 5 seconds
- **Dark mode** toggle with persistent theme preference (saved to `localStorage`)

## Prerequisites

- [Docker](https://docker.com) and [Docker Compose](https://docs.docker.com/compose/) installed and **running**
- The `docker-compose.yaml` file at the project root
- For **local** mode only: [Python 3](https://python.org) installed on your system

> **Docker must already be running before you start the controller.** A Linux container cannot launch Docker Desktop on the host, and the controller container cannot exist while the daemon is down. This is the one genuine chicken-and-egg in the design: `start.sh` checks for it up front and tells you to start Docker Desktop first. In **local** mode the app can start Docker Desktop for you via the UI's *Check Docker / Start If Needed* button — that capability is unavailable once containerized.

## Quick start

```bash
./start.sh              # prompts: 1) docker  2) local
./start.sh docker       # run in a container (recommended)
./start.sh local        # run directly with Python
```

**Windows:** `start.bat` (same options).

Then open [http://localhost:9500](http://localhost:9500).

Once you have run `./start.sh docker` at least once, follow-up commands work without any extra setup (a gitignored `.env` is written with the resolved paths):

```bash
docker compose -f docker-compose.controller.yaml logs -f controller
docker compose -f docker-compose.controller.yaml ps
docker compose -f docker-compose.controller.yaml down     # stop the controller
```

> `.env` stores **absolute** paths. If you move or rename the repo, run `./start.sh docker` again to refresh it.

**Local mode** (manual):

```bash
pip install -r dockercontrolapp/requirements.txt
python dockercontrolapp/app.py
```

> On some systems you may need `pip3` instead of `pip` and `python3` instead of `python` — the helper scripts handle this automatically.

### ⚠️ Security note

The controller container mounts `docker.sock`, which grants **root-equivalent access to the host**. That is inherent to any Docker management UI — it is what lets the app run `docker compose` against your daemon. Treat port 9500 as privileged: don't expose it to a network you don't trust. The controller also runs as `root` inside its container; combined with the socket this is not an additional meaningful boundary, but it is worth knowing before running it anywhere shared.

## Architecture

```
├── docker-compose.yaml           # Managed project (2 services: web, dozzle)
├── docker-compose.controller.yaml# Controller's own project (1 service: controller)
├── dockercontrolapp/             # Flask control app
│   ├── app.py                    # Flask server (port 9500), Docker command executor
│   ├── Dockerfile                # python:3.12-slim + docker CLI + compose plugin
│   ├── .dockerignore
│   ├── requirements.txt          # Flask + PyYAML + gunicorn
│   └── templates/index.html      # Single-page UI
├── angular/                      # Angular build context for the 'web' service
└── start.sh / start.bat          # Launchers (docker | local)
```

### Why the controller is a separate compose project

The controller runs in its own project (`docker-control-app-controller`) rather than being a service in `docker-compose.yaml`. If it were listed there, its own **Stop All** / **Restart All** buttons would stop the very container serving those buttons, with no way back from the UI. Keeping it separate means the controller is never managed by the project it manages, and it never lists itself in the service grid.

### Why the repo is mounted at its identical host path

`docker-compose.controller.yaml` mounts the repo onto itself:

```yaml
volumes:
  - "${REPO_DIR}:${REPO_DIR}"
```

This is deliberate. The compose CLI resolves relative paths (`build.context: angular`, `./angular:/project`) **client-side** into absolute paths, then the daemon bind-mounts those absolute paths on the **host**. If the repo were mounted at some other path (e.g. `/project`), the host would be asked to bind `/project/angular`, which does not exist there, and the `web` service would fail to start. Mounting at the identical path also makes the derived Compose project name match on both sides, so the controller and a host-side `docker compose` always act on the same set of containers.

`start.sh` sets `REPO_DIR` to the absolute repo path and writes it to `.env` for later use.

### Why the image build context is `dockercontrolapp/`

The controller only needs `app.py`, `requirements.txt` and `templates/`. Setting `context: dockercontrolapp` instead of `context: .` keeps the `angular/` tree — including its `node_modules` — out of the build context entirely, which would otherwise be sent to the daemon on every rebuild. The Angular app is built by its own `web` service, not by the controller.

### Why the socket path is derived

Docker Desktop for macOS listens on `~/.docker/run/docker.sock` and does **not** create `/var/run/docker.sock`. Mounting `/var/run/docker.sock` silently yields an empty directory instead of a socket. `start.sh` asks Docker where the active context points:

```bash
docker context inspect "$(docker context show)" --format '{{.Endpoints.docker.Host}}'
```

and exports the result as `DOCKER_SOCK` (defaulting to `/var/run/docker.sock`, which is correct on plain Linux). Both compose files use `${DOCKER_SOCK:-/var/run/docker.sock}`.

### Web server

In container mode the app runs under gunicorn:

```
gunicorn --bind 0.0.0.0:9500 --threads 4 --timeout 660 app:app
```

- `--threads 4` keeps the 5s status polling responsive while a long `compose` command runs.
- `--timeout 660` must exceed `COMPOSE_TIMEOUT` (600s), otherwise gunicorn kills the worker mid-request during a slow `compose up --build`.

In local mode it runs under Flask's development server with `debug=True`.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Liveness + Docker reachability; `503` when Docker is down |
| `/api/services` | GET | List all services from `docker-compose.yaml` with their current status |
| `/api/start-docker-desktop` | POST | Start Docker Desktop — **host mode only**; returns an explanatory message in container mode |
| `/api/ensure-docker-running` | POST | Check Docker; in host mode also waits up to 60s after launching Docker Desktop |
| `/api/start-all` | POST | Start all containers (`docker compose up -d`) |
| `/api/stop-all` | POST | Stop all containers (`docker compose stop`) |
| `/api/restart-all` | POST | Restart all containers (`docker compose restart`) |
| `/api/services/<name>/start` | POST | Start a specific service (`docker compose up -d <name>`) |
| `/api/services/<name>/stop` | POST | Stop a specific service (`docker compose stop <name>`) |
| `/api/services/<name>/logs` | GET | Fetch logs for a container (add `?lines=N`, default 50) |

> The controller container is not part of `docker-compose.yaml`, so it never appears in `/api/services` and is never affected by Stop All / Restart All.

## Docker Compose Operations

```bash
# Start controller
./start.sh docker          # container mode (recommended)
./start.sh local           # host mode with Python

# Controller management
docker compose -f docker-compose.controller.yaml up -d --build
docker compose -f docker-compose.controller.yaml logs -f controller
docker compose -f docker-compose.controller.yaml down

# Managed project operations
docker compose up --build          # or 'docker compose up -d'
docker compose stop                # v2: 'docker compose stop', NOT 'up -d --no-start'
docker compose restart             # Same as 'up --restart'
```

## Services

From `docker-compose.yaml`:

| Service | Type | Port | Build From |
|---------|-------|-------|-------------|
| `web` | Angular SPA | 4200 | `angular/` dir with build target `builder` |
| `dozzle` | Log viewer | 8888 | Docker image: `amir20/dozzle:latest` |

> `deploy: mode: global` on `dozzle` is a Swarm-only key and is ignored by `docker compose`.

## Key Implementation Details

### `dockercontrolapp/app.py`

- **Port:** 9500
- **Logs API:** GET `/api/services/<name>/logs?lines=N`, strips color with `--no-color` flag.
- **Service status:** Uses `docker compose ps --format=json` to parse container states. Since Compose v2.21 this emits **JSON Lines** (one object per line), which is what the parser expects.
- **Docker checks:** `docker info` to verify Docker is running before performing operations.
- **Timeouts:** `COMPOSE_READ_TIMEOUT` (60s) for `ps`/`logs`/`config`; `COMPOSE_TIMEOUT` (600s) for everything else, since a cold image build is slow. Both are env-overridable.
- **Process handling:** compose commands run in a new session and are killed **by process group** on timeout. Killing only the direct child is not sufficient — `docker compose up` spawns grandchildren that inherit the stdout/stderr pipes, so a naive kill leaves those pipes open and the request hangs forever instead of returning an error.
- **Error handling:** all endpoints return JSON, never an HTML 500, so the frontend's `res.json()` cannot throw.

### `dockercontrolapp/templates/index.html`

- Single HTML file with embedded CSS/JS (no external dependencies).
- Polls `/api/services` every 5 seconds to update status badges.
- Log panel auto-refreshes every 5 seconds when open.
- The `web` service is accessed via `http://localhost:4200` (served from the Docker container).
- Suppresses the toast when the Docker check reports exactly `Docker is already running`.

## Verification

After `./start.sh docker`, a healthy system looks like this:

```bash
curl -s localhost:9500/api/health
# {"app":"ok","compose_file":"/abs/path/docker-compose.yaml","docker":"ok","docker_error":"","in_container":true}

curl -s localhost:9500/api/services
# [{"name":"web","status":"running"},{"name":"dozzle","status":"running"}]

docker compose ls -a | grep docker-control-app
# docker-control-app               <- the managed project
# docker-control-app-controller    <- the controller
```

`/api/health` returning `503` means the app is up but the Docker daemon is unreachable — check the `docker_error` field. If `/api/services` ever lists `controller`, something has put the controller into the managed project; that defeats the separation described above.

## Cleaning up stale projects

Renaming or moving the repo leaves the old Compose project behind, along with its containers, because the project name is derived from the directory. Check with `docker compose ls -a`. Any project for this repo whose config file no longer exists is safe to remove:

```bash
docker compose -p <project-name> down --remove-orphans
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `Docker is not running. Start Docker Desktop and try again.` | The daemon is down, so the controller can't even be started | Start Docker Desktop, then re-run `./start.sh docker` |
| `REPO_DIR must be set to the repo root` | Running compose by hand without `.env` | Run `./start.sh docker` once, or `export REPO_DIR=$(pwd)` |
| Controller won't come up after moving/renaming the repo | `.env` holds stale absolute paths | Re-run `./start.sh docker` to refresh it |
| Controller UI shows every service as stopped | `docker` CLI missing or socket not mounted | Check `curl localhost:9500/api/health`; rebuild with `./start.sh docker` |
| Dozzle shows no containers | Socket path wrong for your Docker install | Ensure `DOCKER_SOCK` is set (see above); `docker context inspect "$(docker context show)"` |
| `web` service will not start | Repo not mounted at its host path | Confirm `REPO_DIR` is the absolute repo root |
| Duplicate/ghost containers appear | Managed project name mismatch | `docker compose ls -a` should show exactly `docker-control-app` and `docker-control-app-controller` |
| A start request never returns | Compose build exceeded the timeout | Raise `COMPOSE_TIMEOUT` and gunicorn `--timeout` together |
| Browser shows "Request failed" instead of a message | Controller container is not running | `docker compose -f docker-compose.controller.yaml logs controller` |
| Killed the controller and it won't come back | `restart: unless-stopped` deliberately does **not** restart a container you stopped or killed yourself — only crashes and daemon restarts | Restart it: `docker compose -f docker-compose.controller.yaml up -d` |
| Logs show nothing | Container hasn't written logs yet | Wait a moment after starting the container |

## Screenshot

![screenshot](https://github.com/user-attachments/assets/f2e783c2-9d70-437d-8c61-0828e77149d7)

---

> **Note:** This project is a demo/validation tool. There is no test, lint, typecheck, or CI infrastructure.
