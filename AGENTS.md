# AGENTS.md — Docker Control App

## Project layout

```
├── docker-compose.yaml          # 3 services: web (nginx), backend (Flask), mongo
├── dockercontrolapp/            # Host-side control app (runs outside Docker)
│   ├── app.py                   # Flask server, port 9500
│   ├── requirements.txt         # Flask + PyYAML
│   └── templates/index.html     # Single-page UI, auto-refreshing logs
├── start.sh                     # macOS/Linux launcher (auto-opens browser)
├── start.bat                    # Windows launcher
└── angular/                     # Pre-existing, unrelated
```

## Control app — API

All return JSON. The app sits at the project root and reads `docker-compose.yaml` from there.

| Method | Path | Action |
|---|---|---|
| GET | `/api/services` | List services with status |
| POST | `/api/start-all` | `docker compose up -d` |
| POST | `/api/stop-all` | `docker compose down` |
| POST | `/api/restart-all` | `docker compose restart` |
| POST | `/api/services/<name>/start` | Start one service |
| POST | `/api/services/<name>/stop` | Stop one service |
| GET | `/api/services/<name>/logs?lines=50` | Tail log lines |

## Key details

- Run the control app on the **host**, not in Docker. It shells out to `docker compose`.
- Uses `docker compose` (v2 syntax with space), not `docker-compose` (hyphen).
- The `docker-compose.yaml` references `flask/` and `nginx/` directories that may not exist — compose will fail trying to build/mount them. The control app only reads the YAML to list services; it does not depend on those directories.
- Port 9500 — hardcoded in `app.py`, referenced in scripts and README.
- No test / CI / linter infrastructure. 

## Commands

| Action | Command |
|---|---|
| Start control app | `./start.sh` or `start.bat` |
| Manual start | `pip install -r dockercontrolapp/requirements.txt && python dockercontrolapp/app.py` |
| Compose up | `docker compose up --build` |
| Compose down | `docker compose down` |
