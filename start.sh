#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON=$(command -v python3 || command -v python)
PIP=$(command -v pip3 || command -v pip)
"$PIP" install -r dockercontrolapp/requirements.txt
"$PYTHON" dockercontrolapp/app.py
