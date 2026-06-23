# ADR 001: Use FastAPI For The Backend API

## File Purpose

This Architecture Decision Record explains why ARGUS will use FastAPI for the
backend API layer.

## Why It Exists

Professional engineering teams record important technical decisions so future
contributors understand not only what was chosen, but why it was chosen.

## How It Fits Into The System

FastAPI will become the HTTP gateway for ARGUS. The React frontend will send
requests to FastAPI, and FastAPI will coordinate validation, services, quant
analytics, data access, and AI workflows.

## Status

Accepted

## Context

ARGUS needs a backend framework that can:

- expose REST APIs
- validate request and response data
- support async workflows
- integrate cleanly with Python services
- generate API documentation
- remain approachable for a student developer

The backend will eventually coordinate market data, portfolio analytics,
database access, background work, and AI agent orchestration.

## Decision

Use FastAPI as the backend web framework.

## Reason

FastAPI is a strong fit because it provides:

- first-class type-hint support
- Pydantic-based validation
- async endpoint support
- automatic OpenAPI documentation
- clean dependency injection patterns
- high performance compared with many traditional Python web frameworks

This matches ARGUS's educational and architectural goals. It teaches modern
Python backend engineering while staying practical for production-style APIs.

## Alternatives

### Django

Django is a mature full-stack Python framework with a large ecosystem, built-in
ORM, admin panel, authentication, and many batteries included.

It is excellent for database-heavy web applications, but it can feel heavy for
an API-first research terminal where we want to teach service boundaries and
async workflows explicitly.

### Flask

Flask is lightweight and flexible.

It is useful for small APIs, but many production features such as validation,
documentation, dependency structure, and async support require additional
libraries or custom conventions.

### Express

Express is a popular Node.js backend framework.

It would pair naturally with TypeScript, but ARGUS uses Python heavily for
quantitative finance, data science, and AI workflows, so keeping the backend in
Python reduces integration friction.

## Tradeoffs

FastAPI advantages:

- modern Python typing
- excellent API documentation
- natural fit for async I/O
- good match for AI and data workflows

FastAPI drawbacks:

- smaller ecosystem than Django
- fewer built-in features
- requires deliberate project structure
- async mistakes can still block the event loop

## Industry Usage

FastAPI is commonly used in:

- machine learning APIs
- internal data platforms
- microservices
- AI application backends
- fintech data services

It is popular when teams need Python's data ecosystem and clean HTTP APIs.

## Common Beginner Mistakes

- putting all routes and business logic in `main.py`
- returning raw dictionaries everywhere without response schemas
- mixing database access directly into route handlers
- using `async def` while calling blocking libraries inside
- ignoring error handling and logging

## Interview Perspective

Possible interview question:

> Why did you choose FastAPI over Django or Flask?

Strong answer:

> ARGUS is API-first and Python-heavy. FastAPI gives strong request validation,
> automatic OpenAPI docs, async support, and clean type-driven development. I
> would choose Django if I needed a full monolithic web app with built-in admin
> and authentication from day one.

## Future Improvements

Revisit this decision if ARGUS later needs:

- a built-in admin panel
- complex built-in authentication flows
- a traditional server-rendered web app
- larger plugin ecosystem support

