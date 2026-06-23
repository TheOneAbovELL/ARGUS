# ADR 004: Use Layered Backend Architecture

## File Purpose

This Architecture Decision Record explains why ARGUS separates backend code into
layers such as API routes, schemas, services, models, and core configuration.

## Why It Exists

Phase 2 begins real application code. Without an explicit architecture decision,
it would be easy to place everything inside `main.py` and create a backend that
works briefly but becomes hard to maintain.

## How It Fits Into The System

This ADR guides the structure under `backend/app/`. Future backend modules
should respect these boundaries unless a later ADR changes the decision.

## Status

Accepted

## Context

ARGUS will eventually include:

- HTTP API endpoints
- request and response validation
- market data services
- quantitative analytics
- database models
- AI services
- agent orchestration
- tests

These responsibilities should not live in one file. Each layer needs a clear
job so the system remains readable, testable, and scalable.

## Decision

Use a layered backend architecture:

```text
backend/app/
├── api/
├── core/
├── schemas/
├── services/
├── models/
└── main.py
```

## Layer Responsibilities

### API Layer

Owns HTTP route handlers.

It should:

- define endpoints
- receive validated request models
- call services
- return response models

It should not contain market data fetching, database queries, quant formulas, or
LLM prompts.

### Schema Layer

Owns API data contracts.

It should:

- define request shapes
- define response shapes
- validate input
- document API expectations

### Service Layer

Owns business logic.

It should:

- fetch market data
- coordinate external providers
- call quant modules later
- hide provider details from route handlers

### Model Layer

Owns domain and persistence models.

In Phase 2 this folder is a placeholder. In later phases it may contain
SQLAlchemy models or domain objects.

### Core Layer

Owns infrastructure-level configuration.

It should:

- define application settings
- centralize environment-based configuration
- support future logging and security setup

### Application Entry Point

`main.py` owns FastAPI app creation and router registration.

It should stay small.

## Alternatives

### Single File Application

Everything could live in `main.py`.

This is fast for a tiny demo but breaks down as soon as validation, services,
tests, database logic, and AI orchestration appear.

### Framework-Driven Monolith

A framework such as Django could impose a larger built-in structure.

ARGUS uses FastAPI to keep the API-first design clear and lightweight.

### Microservices

Each subsystem could become a separate service.

That would be premature for Phase 2. ARGUS needs clean internal layers before
distributed services.

## Tradeoffs

Advantages:

- easier testing
- clearer imports
- better separation of concerns
- safer future expansion
- easier interview explanation

Drawbacks:

- more files at the beginning
- requires discipline to maintain boundaries
- may feel slower than writing everything in one file

## Industry Usage

Layered architecture appears in many production systems:

- controllers call services
- services call repositories or providers
- schemas define contracts
- models represent durable or domain entities

FastAPI does not force this structure. Professional teams choose it because it
keeps systems understandable as they grow.

## Common Beginner Mistakes

- putting business logic inside route handlers
- making schemas perform external API calls
- letting services return inconsistent raw dictionaries
- importing route modules from services
- creating circular imports between layers
- adding a database model before knowing the domain shape

## Interview Perspective

Possible interview question:

> Why did you split the backend into API, schemas, services, models, and core?

Strong answer:

> Each layer owns a different responsibility. Routes handle HTTP, schemas define
> contracts, services own business logic, models represent domain or persistence
> objects, and core owns configuration. This keeps the backend testable and
> prevents `main.py` from becoming a giant file.

## Future Improvements

Later phases may add:

- repositories for database access
- dependency injection helpers
- quant modules
- background worker modules
- agent orchestration modules
- structured logging configuration

