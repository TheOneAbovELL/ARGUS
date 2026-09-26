# ARGUS System Context

## File Purpose

This file shows the high-level system context for ARGUS.

## Why It Exists

A system context diagram explains how major parts of the system relate to each
other. It avoids the beginner mistake of thinking only in terms of files instead
of system boundaries.

## How It Fits Into The System

This diagram will evolve every phase. In Phase 1, it is intentionally simple.
In later phases, it will include the database, quant engine, agents, RAG layer,
real-time streaming, and deployment infrastructure.

## Phase 1 Context

```text
User
  |
  v
React Frontend
  |
  | HTTP / JSON
  v
FastAPI Backend
  |
  +------------------+
  |                  |
  v                  v
Market Data       PostgreSQL
Service           Database
  |
  v
LLM Layer
```

## What Each Part Means

### User

The person using ARGUS to research stocks, analyze portfolios, and inspect AI
research output.

### React Frontend

The browser application. It owns visual interaction:

- forms
- dashboards
- charts
- loading states
- error states
- terminal-style workspaces

It should not own secrets, database access, or trusted financial computation.

### FastAPI Backend

The controlled gateway into the system.

It owns:

- request validation
- API contracts
- service coordination
- security boundaries
- structured responses
- future authentication

### Market Data Service

The backend service responsible for retrieving market data from providers such
as yfinance in early phases.

It keeps data-provider logic separate from API route handlers.

### PostgreSQL Database

The durable structured data store.

It will eventually store:

- users
- portfolios
- holdings
- reports
- watchlists
- analysis history
- agent runs

### LLM Layer

The layer responsible for language generation and explanation.

Important rule:

Python computes financial metrics. The LLM explains them.

## Current Phase Boundary

Phase 1 only documents this context.

Phase 2 will implement the first real path:

```text
Client request
  |
  v
FastAPI endpoint
  |
  v
Market Data Service
  |
  v
Structured JSON response
```

No AI, agents, database, or RAG should be implemented in Phase 2.

## Scaling Perspective

At one user, the diagram can run locally.

At many users, this context may grow into:

```text
Browser
  |
  v
Load Balancer
  |
  v
FastAPI Instances
  |
  +--> PostgreSQL
  +--> Redis
  +--> Background Workers
  +--> Market Data Providers
  +--> LLM Providers
  +--> Vector Database
```

The simple Phase 1 diagram prepares us for that future without adding
unnecessary infrastructure too early.

## Common Beginner Mistakes

- letting React call private APIs directly
- putting market data calls directly inside route handlers
- adding a database before knowing what must persist
- adding agents before deterministic services exist
- mixing LLM explanations with mathematical computation

## Future Improvements

Update this document at the end of every phase:

- Phase 2: add implemented backend flow
- Phase 3: add Quant Engine
- Phase 4: add PostgreSQL and ORM layer
- Phase 6: add Agent Coordinator
- Phase 7: add Vector Database
- Phase 8: add WebSocket streaming

