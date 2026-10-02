import os
import signal
import subprocess
import json
import time
from pathlib import Path

import yaml
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

DIR = Path(__file__).resolve().parent.parent
COMPOSE_FILE = os.environ.get('COMPOSE_FILE', str(DIR / 'docker-compose.yaml'))

# Set by docker-compose.controller.yaml. When running in a container we cannot
# launch Docker Desktop (no access to the macOS host), and Docker must already
# be running anyway for this container to exist in the first place.
IN_CONTAINER = os.environ.get('IN_CONTAINER') == '1'

# `docker compose ps`/`logs` must stay snappy; `up` may need to build images,
# which is slow on a cold cache.
COMPOSE_READ_TIMEOUT = int(os.environ.get('COMPOSE_READ_TIMEOUT', 60))
COMPOSE_TIMEOUT = int(os.environ.get('COMPOSE_TIMEOUT', 600))


def get_services():
    try:
        with open(COMPOSE_FILE) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f'Compose file not found: {COMPOSE_FILE}. When running in Docker the '
            'repo must be mounted at the same path as the host, and COMPOSE_FILE '
            'must point inside it.'
        )
    except yaml.YAMLError as e:
        raise ValueError(f'Could not parse {COMPOSE_FILE}: {e}')
    return list(data.get('services', {}).keys())


def check_docker_status():
    try:
        result = subprocess.run(['docker', 'info'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return True, ''
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, 'Docker command timed out'
    except FileNotFoundError:
        return False, 'Docker not found. Is Docker installed?'


def docker_unreachable_error():
    """Return a Flask JSON response describing why Docker is unusable, or None if
    it is usable. Returning JSON keeps the frontend's `res.json()` from throwing
    on an HTML 500 page."""
    ok, err = check_docker_status()
    if ok:
        return None
    if IN_CONTAINER:
        msg = ('Docker daemon is not reachable from the controller container. '
               'Start Docker Desktop, then restart the controller.')
    else:
        msg = 'Docker is not running. Start Docker Desktop and try again.'
    return jsonify({'success': False, 'message': f'{msg} ({err})' if err else msg})


def run_compose(cmd):
    """Run a `docker compose` subcommand and capture its output.

    Uses a new session plus a process-group kill on timeout. Killing only the
    direct child is not enough: `docker compose up` spawns grandchildren that
    inherit the stdout/stderr pipes, so a naive kill leaves those pipes open and
    communicate() would block forever instead of returning a timeout error.

    Read-only queries get a short timeout so the UI stays responsive; build/start
    commands get a long one because a cold image build is slow.
    """
    timeout = COMPOSE_READ_TIMEOUT if cmd[0] in ('ps', 'logs', 'config') else COMPOSE_TIMEOUT
    try:
        proc = subprocess.Popen(
            ['docker', 'compose', '-f', COMPOSE_FILE] + cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            start_new_session=(os.name == 'posix'),
        )
    except FileNotFoundError:
        return False, '', 'Docker not found. Is Docker installed?'

    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == 'posix':
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
        else:
            proc.kill()
        try:
            out, err = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            out, err = '', ''
        return False, out.strip(), (err.strip() or f'Command timed out after {timeout}s')

    return proc.returncode == 0, out.strip(), err.strip()


def get_service_status():
    ok, stdout, _ = run_compose(['ps', '--format', 'json'])
    if not ok:
        return {}

    status_map = {}
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            svc = entry.get('Service', '')
            state = entry.get('State', 'unknown').lower()
            if svc:
                status_map[svc] = state
        except json.JSONDecodeError:
            continue
    return status_map


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/services')
def list_services():
    try:
        services = get_services()
    except (FileNotFoundError, ValueError) as e:
        return jsonify({'error': str(e), 'services': []}), 500
    status = get_service_status()
    return jsonify([
         {'name': svc, 'status': status.get(svc, 'stopped')}
        for svc in services
      ])


@app.route('/api/start-docker-desktop', methods=['POST'])
def start_docker_desktop():
    if IN_CONTAINER:
        return jsonify({
            'success': False,
            'message': 'Cannot launch Docker Desktop from inside a container. '
                       'Start Docker Desktop on the host, then restart the controller.'
        })
    try:
        subprocess.run(['open', '-a', 'Docker'], check=True)
        return jsonify({'success': True, 'message': 'Attempting to start Docker Desktop...'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to start Docker Desktop: {str(e)}'})


@app.route('/api/ensure-docker-running', methods=['POST'])
def ensure_docker_running():
    # First check if Docker is already running
    docker_running, err = check_docker_status()
    if docker_running:
        return jsonify({'success': True, 'message': 'Docker is already running'})

    # In a container we cannot start Docker Desktop, and we could not be running
    # at all if the daemon were down. Report it clearly instead.
    if IN_CONTAINER:
        return jsonify({
            'success': False,
            'message': 'Docker daemon is not reachable from the controller container. '
                       'Start Docker Desktop on the host, then restart the controller.'
                       + (f' ({err})' if err else '')
        })

    # Docker not running, try to start Docker Desktop
    try:
        subprocess.run(['open', '-a', 'Docker'], check=True)
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to start Docker Desktop: {str(e)}'})

    # Wait for Docker to be ready (up to 60 seconds)
    for _ in range(30):
        time.sleep(2)
        docker_running, _ = check_docker_status()
        if docker_running:
            break
    else:
        return jsonify({'success': False, 'message': 'Docker Desktop did not start in time'})

    return jsonify({'success': True, 'message': 'Docker is now running'})


@app.route('/api/start-all', methods=['POST'])
def start_all():
    ok, out, err = run_compose(['up', '-d'])
    message = out if out else ('Containers started successfully' if ok else err)
    return jsonify({'success': ok, 'message': message})


@app.route('/api/stop-all', methods=['POST'])
def stop_all():
    unreachable = docker_unreachable_error()
    if unreachable:
        return unreachable
    ok, out, err = run_compose(['stop'])
    return jsonify({'success': ok, 'message': out if ok else err})


@app.route('/api/restart-all', methods=['POST'])
def restart_all():
    ok, out, err = run_compose(['restart'])
    return jsonify({'success': ok, 'message': out if ok else err})


@app.route('/api/services/<name>/start', methods=['POST'])
def start_service(name):
    ok, out, err = run_compose(['up', '-d', name])
    return jsonify({'success': ok, 'message': out if ok else err})


@app.route('/api/services/<name>/stop', methods=['POST'])
def stop_service(name):
    unreachable = docker_unreachable_error()
    if unreachable:
        return unreachable
    ok, out, err = run_compose(['stop', name])
    return jsonify({'success': ok, 'message': out if ok else err})


@app.route('/api/services/<name>/logs')
def service_logs(name):
    lines = request.args.get('lines', 50, type=int)
    ok, out, err = run_compose(['logs', '--tail', str(lines), '--no-color', name])
    if not ok and not out:
        return jsonify({'logs': err or 'No logs available'})
    return jsonify({'logs': out})


@app.route('/api/health')
def health():
    running, err = check_docker_status()
    return jsonify({
        'app': 'ok',
        'in_container': IN_CONTAINER,
        'compose_file': COMPOSE_FILE,
        'docker': 'ok' if running else 'unreachable',
        'docker_error': err,
    }), (200 if running else 503)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9500, debug=True)
