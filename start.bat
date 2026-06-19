@echo off
cd /d "%~dp0"
pip install -r dockercontrolapp\requirements.txt
python dockercontrolapp\app.py
