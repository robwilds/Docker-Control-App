#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON=$(command -v python3 || command -v python)
PIP=$(command -v pip3 || command -v pip)
"$PIP" install -r dockercontrolapp/requirements.txt
"$PYTHON" dockercontrolapp/app.py &
sleep 2
if [[ "$OSTYPE" == "darwin"* ]]; then
  open http://localhost:9500
else
  xdg-open http://localhost:9500 2>/dev/null || echo "Open http://localhost:9500 in your browser"
fi
wait
