# AGENTS.md — Docker Control App

## Architecture

**Flask web app** that reads `docker-compose.yaml` from repo root and shells out to `docker compose v2` commands. Runs either in a container (recommended) or directly on the host with Python.

```
├── docker-compose.yaml           # Managed project (2 services)
├── docker-compose.controller.yaml# Controller's own project (1 service: controller)
├── dockercontrolapp/             # Control app
│   ├── app.py                    # Flask server (port 9500)
│   ├── Dockerfile                # python:3.12-slim + docker CLI + compose plugin
│   ├── .dockerignore
│   ├── requirements.txt          # Flask + PyYAML + gunicorn
│   └── templates/index.html      # Single-page UI
├── angular/                      # Angular build context for web service
└── start.sh / start.bat         # Launchers (docker | local mode picker)
```

### Two compose projects, on purpose

| File | Project name | Contents |
|------|--------------|----------|
| `docker-compose.yaml` | `docker-control-app` | `web`, `dozzle` — the managed project |
| `docker-compose.controller.yaml` | `docker-control-app-controller` | `controller` — the UI |

The controller is **not** a service in `docker-compose.yaml`. If it were, its own Stop All / Restart All buttons would stop the container serving those buttons with no way back from the UI. As a result the controller never lists itself in `/api/services` and is never touched by Stop All / Restart All.

### The repo is mounted at its identical host path

`"${REPO_DIR}:${REPO_DIR}"` — deliberate, not a shortcut. The compose CLI resolves relative paths (`build.context: angular`, `./angular:/project`) client-side into absolute paths, then the daemon bind-mounts those absolute paths on the **host**. Mounting the repo at any other path (e.g. `/project`) would make the host try to bind `/project/angular`, which does not exist there. It also keeps the derived project name identical on both sides.

`start.sh` exports `REPO_DIR` and writes it plus `DOCKER_SOCK` to a gitignored `.env`.

### Socket path is derived, never hardcoded

Docker Desktop for macOS listens on `~/.docker/run/docker.sock` and does **not** create `/var/run/docker.sock`; mounting that path silently yields an empty directory. `start.sh` resolves it via `docker context inspect "$(docker context show)"`. Both compose files use `${DOCKER_SOCK:-/var/run/docker.sock}` (the default is correct on plain Linux).

### Build context is `dockercontrolapp/`, not the repo root

The controller needs only `app.py`, `requirements.txt` and `templates/`. Using the repo root as context would ship `angular/` — including `node_modules` — to the daemon on every rebuild.

### Bootstrap order is a hard constraint

Docker must be running **before** the controller starts. A Linux container cannot launch Docker Desktop, and the controller container cannot exist while the daemon is down. `start.sh` checks this and fails with a clear message. The app's *Check Docker / Start If Needed* button only works in local mode; in container mode `IN_CONTAINER=1` turns that into a message pointing the user at Docker Desktop.

## Services

Actual services from `docker-compose.yaml`:

| Service | Type | Port | Build From |
|---------|-------|-------|-------------|
| web     | Angular SPA | 4200 | `angular/` dir with build target `builder` |
| dozzle  | Log viewer | 8888 | Docker image: `amir20/dozzle:latest` |

**Do not reference nginx, backend, or mongo** — they don't exist in this compose file.

`deploy: mode: global` on `dozzle` is a Swarm-only key; `docker compose` ignores it.

## Commands

```bash
# Start controller
./start.sh docker          # container mode (recommended)
./start.sh local           # host mode with Python
./start.sh                 # interactive prompt

start.bat                  # Windows, same options

# Controller management
docker compose -f docker-compose.controller.yaml up -d --build
docker compose -f docker-compose.controller.yaml logs -f controller
docker compose -f docker-compose.controller.yaml down

# Managed project operations
docker compose up --build          # or 'docker compose up -d'
docker compose stop                # v2: 'docker compose stop', NOT 'up -d --no-start'
docker compose restart             # Same as 'up --restart'
```

## Key Implementation Details

- **Port**: 9500
- **Logs API**: GET `/api/services/<name>/logs?lines=N`, strips color with `--no-color` flag
- **Network isolation**: Docker creates its own network per compose project
- **WSGI**: gunicorn `--bind 0.0.0.0:9500 --threads 4 --timeout 660 app:app`. `--timeout` must exceed `COMPOSE_TIMEOUT` (600s) or the worker dies mid-build; `--threads` keeps 5s status polling responsive. Local mode uses Flask's dev server with `debug=True`.
- **Timeouts**: `COMPOSE_READ_TIMEOUT` (60s) for `ps`/`logs`/`config`; `COMPOSE_TIMEOUT` (600s) for everything else. Env-overridable.
- **Process handling**: compose commands run via `Popen(start_new_session=True)` and are killed **by process group** on timeout. Killing only the direct child deadlocks: `docker compose up` spawns grandchildren holding the stdout/stderr pipes, so `communicate()` blocks forever and the request never returns.
- **`docker compose ps --format json`** emits **JSON Lines** since Compose v2.21 — the per-line parser in `get_service_status()` is correct for modern compose.
- **Error handling**: every endpoint returns JSON, never an HTML 500, so the frontend's `res.json()` cannot throw. `docker_unreachable_error()` guards Stop All / per-service Stop.
- **Container mode**: `IN_CONTAINER=1` makes `/api/start-docker-desktop` and `/api/ensure-docker-running` return explanatory messages — a Linux container cannot launch macOS Docker Desktop, and Docker must already be running for the container to exist.
- **`restart: unless-stopped`**: recovers from crashes and Docker daemon restarts, but deliberately does *not* restart a container the user stopped or `docker kill`ed. Verified empirically.

## Testing & Quality

No test, lint, typecheck, or CI infrastructure in this repo. Treat as demo/validation tool only.

**Do not run linters/formatting tests** — they don't exist and aren't expected.

Verify changes manually against a running controller:

```bash
curl -s localhost:9500/api/health        # app + Docker reachability
curl -s localhost:9500/api/services      # web + dozzle only, no controller
docker compose ls -a                      # exactly docker-control-app + -controller
```

`docker compose ls -a` showing a third project whose config path no longer exists is a leftover from a renamed/moved checkout. Clean it with `docker compose -p <name> down --remove-orphans`.

**Security**: the controller mounts `docker.sock`, which is root-equivalent access to the host. Never suggest exposing port 9500 to an untrusted network.

**Stale generated file**: `.env` (gitignored) holds absolute `REPO_DIR`/`DOCKER_SOCK` paths. It must be regenerated via `./start.sh docker` if the repo is moved or renamed — do not commit it.