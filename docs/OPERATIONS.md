# Operations: Running, Configuring, Testing, Deploying

Everything below uses free resources only.

## Local development

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate     # Git Bash; PowerShell: .venv\Scripts\Activate.ps1; macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env              # optional; defaults work
uvicorn app.main:app --reload --port 8000
```

* API docs: http://localhost:8000/docs (generated OpenAPI).
* Offline mode with synthetic data: `ARGUS_MARKET_DATA_PROVIDER=fixture`.
* The SQLite database, Chroma index, and uploads live in `backend/.argus/`
  (gitignored). Migrations are applied on startup when `ARGUS_AUTO_MIGRATE=true`.
* Frontend: see `frontend/README.md`. `npm run build` at the repository root
  exports the UI into `backend/app/static`, which the API then serves at
  http://localhost:8000.

## Configuration

All settings are `ARGUS_*` environment variables (or `backend/.env`). The
annotated reference is [`backend/.env.example`](../backend/.env.example).
None is required. Key ones:

| Variable | Default | Purpose |
|---|---|---|
| `ARGUS_MARKET_DATA_PROVIDER` | `yfinance` | `yfinance` (free, delayed) or `fixture` (synthetic, offline) |
| `ARGUS_DATABASE_URL` | SQLite in data dir | e.g. `postgresql+psycopg://user:pass@host/db` |
| `ARGUS_DATA_DIR` | `backend/.argus` | DB, Chroma, uploads |
| `ARGUS_EMBEDDING_PROVIDER` | `onnx` | `onnx` (local MiniLM) or `hash` (tests/offline) |
| `ARGUS_SEC_USER_AGENT` | unset | Enables EDGAR filings; must include a contact email |
| `ARGUS_LLM_PROVIDER` | `none` | `openai_compatible` for a local server or free-tier endpoint |
| `ARGUS_LLM_BASE_URL` / `_MODEL` / `_API_KEY` | Ollama URL / unset / unset | Endpoint, model, and key (keys only in `backend/.env`, which is gitignored) |
| `ARGUS_LLM_ALLOW_REMOTE` | `false` | Must be `true` for a non-localhost endpoint such as Groq |
| `ARGUS_API_RATE_LIMIT_PER_MINUTE` | `120` | Per-client limit on provider-backed public routes |
| `ARGUS_CORS_ORIGINS` | localhost:3000 | JSON list of allowed origins |
| `ARGUS_SESSION_COOKIE_SECURE` | `false` | Set `true` behind HTTPS |
| `ARGUS_LOG_JSON` | `false` | Structured JSON logs |
| `ARGUS_AUTO_MIGRATE` | `true` | Containers set `false` and migrate explicitly |

## Database migrations

```bash
cd backend
alembic upgrade head          # apply
alembic check                 # fail if models drifted from migrations
alembic downgrade base        # roll everything back (destructive)
alembic revision --autogenerate -m "describe change"   # then review the file
```

Migrations are tested on SQLite in every test run. They are also tested on
PostgreSQL when `ARGUS_TEST_POSTGRES_URL` is set (CI provides a Postgres
service). Rendering the PostgreSQL DDL with `alembic upgrade head --sql` was
verified locally. Running against a live PostgreSQL server was **not** possible
in the development environment (no Docker or Postgres installed); the CI
workflow is configured to run it against a PostgreSQL service.

## Tests and quality gates

```bash
cd backend
pytest -q                                    # offline: fixtures, temp SQLite, in-memory Chroma
ARGUS_RUN_LIVE_TESTS=1 pytest -m integration # optional live check against free Yahoo data
python -m evals.research_eval                # research grounding evaluation
ruff check app tests evals migrations/env.py # lint
```

Browser tests: see the README (`npm run test:e2e` in `frontend/`).

### Dependency pins

`requirements.txt` pins direct dependencies; `constraints.txt` pins the full
transitive set the test suite ran against, and Docker and CI install with
`-c constraints.txt`. After changing requirements, reinstall in a clean virtual
environment, run the tests, and regenerate `constraints.txt` from that
environment (`pip freeze`, limited to the dependency closure of
`requirements-dev.txt`).

### Security-relevant settings

* `ARGUS_CORS_ORIGINS` must list explicit origins; `*` is rejected because
  credentials are allowed.
* `ARGUS_SESSION_COOKIE_SECURE=true` behind HTTPS. The app logs a warning in
  production when it is off.
* `/docs` and `/openapi.json` are disabled when `ARGUS_ENVIRONMENT=production`,
  unless `ARGUS_EXPOSE_API_DOCS=true`.
* Rate limits (per process): sign-in per IP+email and per IP across emails,
  research, market/analytics, and document uploads or SEC imports
  (`ARGUS_UPLOAD_RATE_LIMIT_PER_MINUTE`, default 10).
* Document parsing is bounded. PDFs are limited by pages (600), decompressed
  content per page (2 MB) and per document (50 MB), parse time (120 s), and
  extracted text (3M characters, HTML too). At most two documents are parsed at
  once.

## Docker

```bash
docker compose up --build      # ARGUS + PostgreSQL 16 → http://localhost:8000
```

The image builds the frontend and serves it from the API process, runs as a
non-root user, applies migrations with `alembic upgrade head` before starting,
exposes a `HEALTHCHECK` on `/health/ready`, and shuts down gracefully on SIGTERM.
Persistent data lives in named volumes. The Dockerfile has not been built in
the development environment (Docker is not installed there); the CI workflow
is configured to build it.

## Health, logging, and tracing

* `GET /health`: liveness (process up; checks nothing external).
* `GET /health/ready`: readiness. Pings the database and, if loaded, the
  vector store; returns 503 with component status only (no internals).
* Every response carries `X-Request-ID` (an incoming valid id is reused). The
  id appears in every log line and in error bodies.
* Access logs include method, path, status, and duration. Unexpected exceptions
  are logged with stack traces server-side; clients get a generic 500.

## Operational limits and known constraints

* Caches and rate limiters are in process memory: fine for one process, not
  shared across replicas. Rate limits key on the client IP. Behind a reverse
  proxy, run uvicorn with `--proxy-headers` (the Docker image does) and set
  `--forwarded-allow-ips` to the proxy's address, or every user will share one
  bucket.
* `backend/api/index.py` (Vercel) remains from the earlier deployment, but
  serverless instances have no persistent disk: without `ARGUS_DATABASE_URL`
  and external storage, accounts, documents, and the vector index do not
  survive between instances. Use the Docker image for a real deployment.
* Groq's free tier allows about 8,000 tokens per minute for `gpt-oss-120b`,
  roughly one LLM-synthesized report per minute. Requests beyond that wait for
  the reset or fall back to the deterministic report.
* Yahoo Finance is unofficial and rate limited. Calls are serialized (yfinance
  shares a non-thread-safe HTTP session), bounded by a per-attempt timeout
  (12 s) and an overall deadline (45 s), and retried with backoff. Abandoned
  calls stop retrying once their deadline passes. On a slow network, long
  histories (e.g. the 2007–2022 stress window) can time out; ARGUS reports a
  504 rather than partial data.
* With `ARGUS_EMBEDDING_PROVIDER=onnx` (the default), the MiniLM model (about
  80 MB) downloads in the background on first start. Document upload and
  search return 503 `embedding_model_unavailable` until it is ready, and
  `/api/system/status` shows progress. On slow networks, pre-fetch it with
  `python -m app.knowledge.model_cache`, which is resumable, or use
  `ARGUS_EMBEDDING_PROVIDER=hash`.
