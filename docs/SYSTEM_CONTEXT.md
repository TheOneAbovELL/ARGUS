# ARGUS System Context

The phase-1 sketch that used to live here (React → FastAPI → PostgreSQL + LLM
layer) has been superseded by the implemented system. The current, verified
system context, component boundaries, request flows, persistence model, and
auth boundary are in [ARCHITECTURE.md](ARCHITECTURE.md).

Summary: a Next.js static UI calls a FastAPI service that owns all trusted
computation (quant and portfolio engines), research orchestration with an
evidence ledger and claim validator, market data from free sources with
provenance and caching, a local document index (ChromaDB + local embeddings),
and relational persistence (SQLite or PostgreSQL via Alembic). An optional
language model is optional and must be local, or an explicitly allowed free-tier endpoint (`ARGUS_LLM_ALLOW_REMOTE=true`); no paid API is used.
