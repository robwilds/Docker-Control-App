# AGENTS.md — Docker Control App

## Architecture

**Host-side Flask web app** that reads `docker-compose.yaml` from repo root and shells out to `docker compose v2` commands. Never runs inside Docker.

```
├── docker-compose.yaml           # Project definition (2 services)
├── dockercontrolapp/             # Host control app
│   ├── app.py                    # Flask server (port 9500)
│   ├── requirements.txt          # Flask + PyYAML
│   └── templates/index.html      # Single-page UI
├── angular/                      # Angular build context for web service
└── start.sh / start.bat         # Launchers (auto-install deps, open browser)
```

## Services

Actual services from `docker-compose.yaml`:

| Service | Type | Port | Build From |
|---------|-------|-------|-------------|
| web     | Angular SPA | 4200 | `angular/` dir with build target `builder` |
| dozzle  | Log viewer | 8888 | Docker image: `amir20/dozzle:latest` |

**Do not reference nginx, backend, or mongo** — they don't exist in this compose file.

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

## Key Implementation Details

- **Port**: 9500 (hardcoded in app.py)
- **Volume mounts**: `./angular:/project` and `/project/node_modules` — ensure these paths exist on your host before starting web service
- **Logs API**: GET `/api/services/<name>/logs?lines=N`, strips color with `--no-color` flag
- **Network isolation**: Docker creates its own network for compose projects

## Testing & Quality

No test, lint, typecheck, or CI infrastructure in this repo. Treat as demo/validation tool only.

**Do not run linters/formatting tests** — they don't exist and aren't expected.
