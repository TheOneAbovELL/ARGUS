# ARGUS Learning Journal

## File Purpose

This file tracks what is being learned while building ARGUS.

## Why It Exists

A learning journal turns the project into interview evidence. It helps explain
not just what was built, but how understanding improved over time.

## How It Fits Into The System

This document should be updated weekly or at the end of each major phase. It is
not application code, but it supports the educational mission of ARGUS.

## Week 1: Phase 1 Foundations

### Learned

- HTTP is the request-response protocol used by browsers and servers.
- REST is a resource-oriented style for designing APIs.
- JSON is the data format ARGUS will use for most API payloads.
- The frontend owns user interaction and visualization.
- The backend owns validation, trusted computation, storage, and security.
- PostgreSQL is useful for durable structured data with relationships.
- Async programming helps servers handle many waiting tasks efficiently.
- LLMs should explain financial metrics, not invent deterministic calculations.

### Still Confused

- Async programming versus parallel CPU execution.
- How SQLAlchemy maps Python classes to database tables.
- When WebSockets are better than normal HTTP.
- How agents should be designed so they are reliable instead of vague prompts.

### Questions

- Why use SQLAlchemy instead of writing raw SQL everywhere?
- When should ARGUS introduce PostgreSQL?
- What data should be persisted first?
- How do we test FastAPI endpoints?
- How will the frontend and backend share type expectations?

### Interview Notes

If asked why ARGUS needs a backend:

> The frontend should not directly call Gemini, market APIs, or the database
> because API keys would be exposed, business logic would become scattered, and
> validation would be difficult. The backend acts as a controlled gateway.

If asked why Gemini should not calculate Sharpe Ratio:

> LLMs generate text. Sharpe Ratio is mathematics. Financial metrics must be
> deterministic. Python computes the metric, and the LLM explains the result.

If asked why PostgreSQL instead of JSON files:

> ARGUS needs relationships, indexing, querying, transactions, and scalability.
> JSON files become unmanageable quickly as portfolios, holdings, reports, and
> users grow.

## Weekly Template

Copy this template for future weeks:

```markdown
## Week N: Topic

### Learned

- ...

### Still Confused

- ...

### Questions

- ...

### Interview Notes

- ...

### Code Built

- ...

### Bugs Encountered

- ...
```

## Future Improvements

Add one entry at the end of every phase:

- what was built
- what was hard
- what changed in your understanding
- what interview story came out of the work

