# ARGUS Project Constitution

## File Purpose

This file defines the operating rules for ARGUS.

## Why It Exists

Large projects fail when the team starts coding before agreeing on purpose,
architecture, learning goals, and constraints. This constitution keeps the
project focused and prevents shortcuts that would make the system less useful
as a serious portfolio project.

## How It Fits Into The System

This document is the source of truth for how ARGUS should be built. Future
technical documents, backend modules, frontend components, database migrations,
and agent workflows should follow these principles.

## Project Identity

Project name: ARGUS

Full name: ARGUS — Multi-Agent Quantitative Research Terminal

Mission: Build an institutional-style AI-powered research terminal that combines
quantitative analytics, financial data engineering, retrieval systems, agent
orchestration, and modern full-stack architecture.

ARGUS is inspired by:

- Bloomberg Terminal
- Perplexity-style research workflows
- institutional quant research systems
- modern AI agent architectures

ARGUS is not only a chatbot. ARGUS should become an integrated research system
where structured data, quantitative computation, retrieval, and specialized
agents work together.

## Primary Educational Objective

The finished codebase is not the only goal. The deeper goal is becoming the
engineer capable of building the codebase.

Every implementation decision should teach:

- what is being built
- why it matters
- how it works internally
- where the pattern appears in industry
- what tradeoffs exist
- how to discuss it in interviews
- how the design changes at larger scale

## Engineering Principles

### Separation Of Concerns

Each module should have one clear responsibility.

Bad example:

```text
main.py
```

containing API routes, data fetching, quant math, AI calls, database logic, and
configuration.

Better example:

```text
backend/
├── app/
│   ├── api/
│   ├── services/
│   ├── quant/
│   ├── schemas/
│   └── core/
```

Each folder owns a specific part of the system.

### Scalability

ARGUS starts with one user, but we design as if the system may eventually serve
many users.

This means:

- validation at API boundaries
- clear service layers
- isolated data access
- async-friendly architecture
- explicit configuration
- logging and observability
- testable business logic

### Maintainability

Code should be understandable six months later.

Prefer:

- clear naming
- type hints
- docstrings
- small functions
- explicit data models
- predictable folder structure

Avoid:

- clever abstractions too early
- giant files
- hidden global state
- unvalidated dictionaries passed through the system
- business logic inside route handlers

### Production Mindset

Even when building an MVP, ARGUS should use habits that scale:

- input validation
- structured error handling
- logging
- tests
- environment-based configuration
- stable API contracts
- documentation

## Development Phases

### Phase 1: Foundations

Goal: Understand the stack before writing significant application code.

Topics:

- HTTP
- REST APIs
- JSON
- frontend/backend responsibilities
- relational databases
- SQL and PostgreSQL
- async programming
- project architecture

Deliverable:

- documentation foundation
- shared vocabulary
- architecture direction

### Phase 2: MVP Research Terminal

Goal: A user enters a ticker and receives a structured analysis.

Initial flow:

```text
React frontend
    |
    v
FastAPI backend
    |
    v
Market data service
    |
    v
LLM service
    |
    v
Structured research response
```

### Phase 3: Quant Engine

Goal: Replace vague AI analysis with real quantitative computation.

Modules:

```text
backend/app/quant/
├── returns.py
├── volatility.py
├── beta.py
├── drawdown.py
├── sharpe.py
└── sortino.py
```

### Phase 4: Database System

Goal: Introduce PostgreSQL, SQLAlchemy, and Alembic.

ARGUS will use a relational database for durable structured data such as users,
portfolios, holdings, watchlists, generated reports, and research history.

### Phase 5: Portfolio Engine

Goal: Analyze a user portfolio instead of a single ticker.

Example input:

```json
{
  "NVDA": 40,
  "MSFT": 30,
  "AAPL": 30
}
```

### Phase 6: Agent Orchestration

Goal: Introduce specialized agents:

- Market Agent
- News Agent
- Risk Agent
- Strategy Agent

### Phase 7: RAG Infrastructure

Goal: Add document retrieval using embeddings and a vector database.

### Phase 8: Real-Time Streaming

Goal: Add terminal-style updates through WebSockets or server-sent events.

### Phase 9: Professional Dashboard

Goal: Build a polished research workspace with multiple panels and workflows.

### Phase 10: Deployment

Goal: Package, deploy, and present ARGUS professionally.

## Architecture Direction

Long-term architecture:

```text
User
  |
  v
React Frontend
  |
  v
FastAPI Gateway
  |
  +--> Quant Engine
  |
  +--> Agent Coordinator
  |
  +--> Market Data Services
  |
  +--> Knowledge Layer
  |
  +--> Persistence Layer
```

## Common Beginner Mistakes This Project Avoids

- Building an LLM wrapper and calling it a research system
- Putting all backend logic in one file
- Letting the frontend invent data shapes instead of using API contracts
- Computing financial metrics without understanding assumptions
- Adding agents before there are deterministic tools for them to use
- Adding databases before understanding what data must persist
- Adding Docker, Redis, Celery, or LangGraph before the core loop works

## Interview Positioning

ARGUS should eventually be explainable as:

> Built ARGUS, a multi-agent quantitative research terminal combining FastAPI,
> React, PostgreSQL, quantitative analytics, retrieval-augmented generation,
> and specialized AI agents for institutional-style market research.

Strong interview themes:

- layered backend architecture
- API design
- quant analytics from first principles
- async workflows
- agent decomposition
- RAG design
- database modeling
- testing and deployment

## Future Improvements

This constitution can later be expanded into separate documents:

- Product Requirements Document
- System Design Document
- API Specification
- Database Design Specification
- Quant Analytics Specification
- Agent Design Specification
- Deployment Runbook

