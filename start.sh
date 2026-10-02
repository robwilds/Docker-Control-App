#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Absolute path to the repo root. Both compose files mount the repo at this exact
# path so that the compose CLI (client side) and the Docker daemon (host side)
# resolve relative paths like ./angular identically.
export REPO_DIR="$(pwd -P)"

usage() {
  cat <<EOF
Usage: ./start.sh [docker|local]

  docker   Run the control app in a container (default recommended)
  local    Run the control app directly with Python (no container)

With no argument you are prompted to choose.
EOF
}

open_browser() {
  if [[ "$OSTYPE" == darwin* ]]; then
    open http://localhost:9500
  else
    xdg-open http://localhost:9500 2>/dev/null || echo "Open http://localhost:9500 in your browser"
  fi
}

# Docker Desktop for macOS exposes the daemon socket at
# ~/.docker/run/docker.sock rather than /var/run/docker.sock. Ask Docker where
# the active context points, and fall back to the conventional Linux path.
detect_docker_sock() {
  local endpoint
  if endpoint=$(docker context inspect "$(docker context show)" \
      --format '{{.Endpoints.docker.Host}}' 2>/dev/null); then
    endpoint="${endpoint#unix://}"
    if [[ -S "$endpoint" ]]; then
      echo "$endpoint"
      return
    fi
  fi
  echo "/var/run/docker.sock"
}

run_docker() {
  command -v docker >/dev/null 2>&1 || { echo "docker not found in PATH" >&2; exit 1; }
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running. Start Docker Desktop and try again." >&2
    exit 1
  fi

  export DOCKER_SOCK="$(detect_docker_sock)"
  echo "Docker socket: $DOCKER_SOCK"
  echo "Repo path:     $REPO_DIR"

  # Persist the interpolated paths so follow-up commands (logs, ps, down) work
  # without re-exporting them. Compose reads .env automatically.
  printf 'REPO_DIR=%s\nDOCKER_SOCK=%s\n' "$REPO_DIR" "$DOCKER_SOCK" > .env

  docker compose -f docker-compose.controller.yaml up -d --build
  open_browser
  echo
  echo "Controller running at http://localhost:9500"
  echo "Logs:     docker compose -f docker-compose.controller.yaml logs -f controller"
  echo "Shutdown: docker compose -f docker-compose.controller.yaml down"
}

run_local() {
  PYTHON=$(command -v python3 || command -v python)
  PIP=$(command -v pip3 || command -v pip)
  "$PIP" install -r dockercontrolapp/requirements.txt
  "$PYTHON" dockercontrolapp/app.py &
  sleep 2
  open_browser
  wait
}

case "${1:-}" in
  docker) run_docker ;;
  local)  run_local ;;
  -h|--help|help) usage ;;
  "")
    echo "How do you want to run the control app?"
    echo "  1) docker  - in a container (recommended)"
    echo "  2) local   - directly with Python"
    read -r -p "Choose [1/2]: " choice
    case "$choice" in
      1|docker) run_docker ;;
      2|local)  run_local ;;
      *) echo "Invalid choice" >&2; exit 1 ;;
    esac
    ;;
  *) usage; exit 1 ;;
esac