## Docker Control App

Web UI to manage Docker Compose services — lists services, shows status, start/stop/restart, and live log tailing.  This can be used with any docker-compose.yaml file as long as it's in the root of the project!

### Prerequisites

- [Python 3](https://python.org) installed on your system
- [Docker](https://docker.com) and [Docker Compose](https://docs.docker.com/compose/) installed
- The `docker-compose.yaml` file at the project root

### Quick start

**Option A — helper scripts (auto-installs dependencies):**

- **macOS / Linux:** `./start.sh`
- **Windows:** `start.bat`

**Option B — manual:**

```bash
pip install -r dockercontrolapp/requirements.txt
python dockercontrolapp/app.py
```

> On some systems you may need `pip3` instead of `pip` and `python3` instead of `python` — the helper scripts handle this automatically.

The helper scripts automatically open [http://localhost:9500](http://localhost:9500) in your browser once the server is ready.
<img width="1151" height="719" alt="image" src="https://github.com/user-attachments/assets/f6c8e113-cc58-40e0-8118-822425e34903" />

---

## Compose sample

### Angular service

Project structure:

```
.
├── angular
│   ├── Dockerfile
│   ├── ...
│   ├── ...
│   ....
└── docker-compose.yaml
```

The compose file defines an application with two services `angular` and dozzle. The image for the angular service is built with the Dockerfile inside the `angular` directory (build parameter).

When deploying the application, docker compose maps the container port 4200 to the same port on the host as specified in the file.
Make sure port 4200 is not being used by another container, otherwise the port should be changed.

```

```
