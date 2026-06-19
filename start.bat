@echo off
cd /d "%~dp0"
pip install -r dockercontrolapp\requirements.txt
start "Docker Control App" python dockercontrolapp\app.py
timeout /t 2 /nobreak >nul
start http://localhost:9500
