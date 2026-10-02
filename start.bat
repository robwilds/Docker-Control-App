@echo off
setlocal
cd /d "%~dp0"

rem Absolute path to the repo root. Both compose files mount the repo at this
rem exact path so the compose CLI and the Docker daemon resolve relative paths
rem like .\angular identically.
for %%I in ("%~dp0.") do set "REPO_DIR=%%~fI"

if /i "%~1"=="docker" goto docker
if /i "%~1"=="local"  goto local

echo How do you want to run the control app?
echo   1) docker  - in a container ^(recommended^)
echo   2) local   - directly with Python
set /p "choice=Choose [1/2]: "
if "%choice%"=="1" goto docker
if "%choice%"=="2" goto local
echo Invalid choice
exit /b 1

:docker
where docker >nul 2>nul
if errorlevel 1 (
  echo docker not found in PATH
  exit /b 1
)
docker info >nul 2>nul
if errorlevel 1 (
  echo Docker is not running. Start Docker Desktop and try again.
  exit /b 1
)

rem Docker Desktop for macOS/Windows listens under %%USERPROFILE%%\.docker\run
rem rather than /var/run/docker.sock. Let the user override if needed.
if not defined DOCKER_SOCK (
  if exist "%USERPROFILE%\.docker\run\docker.sock" (
    set "DOCKER_SOCK=%USERPROFILE%\.docker\run\docker.sock"
  ) else (
    set "DOCKER_SOCK=/var/run/docker.sock"
  )
)
echo Docker socket: %DOCKER_SOCK%
echo Repo path:     %REPO_DIR%

rem Persist the interpolated paths so follow-up commands (logs, ps, down) work
rem without re-setting them. Compose reads .env automatically.
> .env echo REPO_DIR=%REPO_DIR%
>> .env echo DOCKER_SOCK=%DOCKER_SOCK%

docker compose -f docker-compose.controller.yaml up -d --build || exit /b 1
start http://localhost:9500
echo.
echo Controller running at http://localhost:9500
echo Logs:     docker compose -f docker-compose.controller.yaml logs -f controller
echo Shutdown: docker compose -f docker-compose.controller.yaml down
exit /b 0

:local
pip install -r dockercontrolapp\requirements.txt || exit /b 1
start "Docker Control App" python dockercontrolapp\app.py
timeout /t 2 /nobreak >nul
start http://localhost:9500
exit /b 0