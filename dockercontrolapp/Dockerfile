FROM python:3.12-slim

# The app shells out to `docker compose`, so the image needs the Docker CLI plus
# the compose plugin. Only the CLI is required: the BuildKit work itself happens
# daemon-side over the mounted socket.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl; \
    install -m 0755 -d /etc/apt/keyrings; \
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc; \
    chmod a+r /etc/apt/keyrings/docker.asc; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
> /etc/apt/sources.list.d/docker.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        docker-ce-cli \
        docker-buildx-plugin \
        docker-compose-plugin; \
    apt-get purge -y --auto-remove curl; \
    rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

EXPOSE 9500

# --timeout must exceed COMPOSE_TIMEOUT (600s by default in app.py), otherwise
# gunicorn kills the worker mid-request during a slow `compose up --build`.
# --threads keeps the UI's 5s status polling responsive during those long calls.
CMD ["gunicorn", "--bind", "0.0.0.0:9500", "--threads", "4", "--timeout", "660", "app:app"]