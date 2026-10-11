# ARGUS — single image serving the API and the exported web UI.
#
#   docker build -t argus .
#   docker compose up            (adds PostgreSQL; see docker-compose.yml)

# ── 1. Build the static frontend ──────────────────────────────────────
FROM node:22-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Same-origin deployment: the UI calls the API on the host that served it.
ENV NEXT_PUBLIC_API_URL=""
RUN npm run build

# ── 2. Python runtime ────────────────────────────────────────────────
FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ARGUS_ENVIRONMENT=production \
    ARGUS_LOG_JSON=true \
    ARGUS_DATA_DIR=/data \
    ARGUS_AUTO_MIGRATE=false

WORKDIR /app/backend
COPY backend/requirements.txt backend/constraints.txt ./
# constraints.txt pins the transitive dependency set the test suite ran against.
RUN pip install -r requirements.txt -c constraints.txt

COPY backend/ ./
COPY --from=frontend /build/frontend/out ./app/static

RUN useradd --create-home --uid 10001 argus \
    && mkdir -p /data /home/argus/.cache/chroma \
    && chown -R argus:argus /data /app /home/argus/.cache
USER argus

EXPOSE 8000
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=4).status == 200 else 1)"

# Migrations are an explicit step, then the server starts. uvicorn handles
# SIGTERM gracefully (finishes in-flight requests, runs lifespan shutdown).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --timeout-graceful-shutdown 20"]
