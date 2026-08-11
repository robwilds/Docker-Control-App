import os
import subprocess
import json
from pathlib import Path

import yaml
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

DIR = Path(__file__).resolve().parent.parent
COMPOSE_FILE = os.environ.get('COMPOSE_FILE', str(DIR / 'docker-compose.yaml'))


def get_services():
    with open(COMPOSE_FILE) as f:
        data = yaml.safe_load(f)
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


def check_docker_running():
    docker_running, _ = check_docker_status()
    if not docker_running:
        raise Exception('Docker is not running')


def run_compose(cmd):
    try:
        result = subprocess.run(
             ['docker', 'compose', '-f', COMPOSE_FILE] + cmd,
            capture_output=True, text=True, timeout=120
         )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, '', 'Command timed out'
    except FileNotFoundError:
        return False, '', 'Docker not found. Is Docker installed?'


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
    services = get_services()
    status = get_service_status()
    return jsonify([
         {'name': svc, 'status': status.get(svc, 'stopped')}
        for svc in services
      ])



@app.route('/api/start-docker-desktop', methods=['POST'])
def start_docker_desktop():
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


import time


@app.route('/api/start-all', methods=['POST'])
def start_all():
    ok, out, err = run_compose(['up', '-d'])
    message = out if out else ('Containers started successfully' if ok else err)
    return jsonify({'success': ok, 'message': message})


@app.route('/api/stop-all', methods=['POST'])
def stop_all():
    check_docker_running()
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
    check_docker_running()
    ok, out, err = run_compose(['stop', name])
    return jsonify({'success': ok, 'message': out if ok else err})


@app.route('/api/services/<name>/logs')
def service_logs(name):
    lines = request.args.get('lines', 50, type=int)
    ok, out, err = run_compose(['logs', '--tail', str(lines), '--no-color', name])
    if not ok and not out:
        return jsonify({'logs': err or 'No logs available'})
    return jsonify({'logs': out})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9500, debug=True)
