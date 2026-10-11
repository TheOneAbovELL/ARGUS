# API Reference

The authoritative, always-current schema is the generated OpenAPI document at
`/docs` (Swagger UI) and `/openapi.json`. This page summarizes conventions and
routes.

## Conventions

* JSON under `/api`; probes at `/health` and `/health/ready`.
* Errors: `{"error": {"code", "message", "details?"}, "request_id"}`. See the
  table in [ARCHITECTURE.md](ARCHITECTURE.md#8-error-semantics).
* Auth: `argus_session` HttpOnly cookie (browser) or `Authorization: Bearer`
  (pass `?return_token=true` to signup/login). Cookie-authenticated
  `POST`/`PUT`/`DELETE` must send `X-ARGUS-CSRF: 1`.
* Return-type numbers are decimals (`0.12` = 12%). Drawdown, VaR, and CVaR are
  negative. Undefined metrics are `null`.
* Market payloads include `provenance {provider, mode, retrieved_at, as_of, cached, stale}`.
* Windows: `period` ∈ `1mo 3mo 6mo ytd 1y 2y 3y 5y 10y max`, or `start`/`end` dates.
* Collections are paginated with `limit`/`offset` and return `page {total, limit, offset}`.

## Routes

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health`, `/health/ready` | – | Liveness / readiness |
| GET | `/api/system/status` | – | Data mode, research mode, enabled features |
| GET | `/api/meta/metrics` | – | Metric formulas and conventions |
| GET | `/api/market/search?q=` | – | Symbol search |
| GET | `/api/market/quotes?symbols=a,b` | – | Batch quotes; per-symbol errors explicit |
| GET | `/api/market/{symbol}/quote` | – | Latest (delayed) quote |
| GET | `/api/market/{symbol}/profile` | – | Classification and key statistics |
| GET | `/api/market/{symbol}/history` | – | Daily OHLCV, adjusted closes, dividends/splits |
| GET | `/api/market/{symbol}/news` | – | Provider headlines with publisher, date, and URL |
| POST | `/api/analytics/asset` | – | Full single-asset analytics with series |
| POST | `/api/portfolio/analyze` | – | Portfolio analytics (two models) |
| POST | `/api/portfolio/stress` | – | Historical stress-episode replay |
| GET/POST | `/api/portfolios` | ✓ | List / create saved portfolios |
| GET/PUT/DELETE | `/api/portfolios/{id}` | ✓ | Read / update (with `version`) / delete |
| GET/POST | `/api/watchlist` | ✓ | List / add (idempotent) |
| DELETE | `/api/watchlist/{symbol}` | ✓ | Remove |
| POST | `/api/research` | optional | Grounded research report (saved when signed in) |
| POST | `/api/research/stream` | optional | Same, with SSE `step` events, then `report` or `error` |
| GET | `/api/research` | ✓ | Research history |
| GET/DELETE | `/api/research/{id}` | ✓ | Saved report snapshot |
| POST | `/api/documents` | ✓ | Upload and index (PDF/TXT/MD/HTML) |
| GET | `/api/documents` | ✓ | List documents |
| GET/DELETE | `/api/documents/{id}` | ✓ | Metadata / delete (index and file) |
| GET | `/api/documents/{id}/file` | ✓ | Original file (sandboxed) |
| POST | `/api/documents/search` | ✓ | Passage search with provenance |
| GET | `/api/filings/{symbol}` | – | Recent SEC filings (needs `ARGUS_SEC_USER_AGENT`) |
| POST | `/api/documents/import-sec` | ✓ | Import a filing as a document |
| POST | `/api/auth/signup`, `/login`, `/logout` | – | Session lifecycle |
| GET | `/api/auth/me` | ✓ | Current user |

## Example

```bash
curl -s localhost:8000/api/analytics/asset \
  -H 'Content-Type: application/json' \
  -d '{"symbol": "AAPL", "period": "1y", "benchmark": "SPY", "risk_free_rate": 0.04}'
```

The pre-redesign root routes were replaced: `/analyze` became
`POST /api/analytics/asset`, `/portfolio/analyze` became
`POST /api/portfolio/analyze`, and `/research` became `POST /api/research`.
They live under `/api` because the SPA's page routes (`/portfolio`,
`/research`) share the same origin.
