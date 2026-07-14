# Slim base image; project pins Python 3.13 (see .python-version / pyproject.toml)
FROM python:3.13-slim

# Install uv (dependency resolver/installer used by this project instead of requirements.txt)
COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /uvx /usr/local/bin/

# Non-root user for running the app
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /usr/sbin/nologin --create-home appuser

WORKDIR /app

# Install dependencies first (layer caching): only pyproject.toml/uv.lock invalidate this layer
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

# Copy application code
COPY app/ ./app/
COPY main.py seed.py ./
COPY messier_catalog.json .

# Create persistent data/upload directories owned by the runtime user
RUN mkdir -p /app/data /app/static/uploads && \
    chown -R appuser:appgroup /app

EXPOSE 8000

USER appuser

ENV PATH="/app/.venv/bin:${PATH}"
# UPLOAD_DIR default in .env.example is relative ("app/static/uploads"), which is only
# correct when the process CWD is the repo root (local dev). Inside this image the app
# package lives at /app/app, so podman-compose.yml overrides UPLOAD_DIR to the absolute
# path /app/static/uploads to avoid resolving to /app/app/static/uploads instead.

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
