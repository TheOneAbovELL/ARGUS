# Phase 1 Foundations

## Goal

Phase 1 builds the conceptual base for ARGUS before significant code is written.

This matters because a production-quality system is not just files and
frameworks. It is a set of cooperating ideas: clients, servers, protocols,
data contracts, persistence, concurrency, and clean boundaries.

## Concepts Being Learned

- HTTP
- REST APIs
- JSON payloads
- frontend/backend separation
- relational databases
- PostgreSQL
- asynchronous programming
- layered architecture

## Architecture Explanation

ARGUS will eventually follow this request flow:

```text
Browser
  |
  | HTTP request
  v
FastAPI route
  |
  | validated Python object
  v
Service layer
  |
  | calls data, quant, or AI tools
  v
Response schema
  |
  | JSON response
  v
Browser UI
```

The important lesson is that each layer has a job.

- The frontend displays information and captures user input.
- The API layer receives requests and validates inputs.
- The service layer performs business logic.
- The quant layer performs deterministic financial computation.
- The persistence layer stores durable structured data.
- The AI layer summarizes, reasons, and generates language.

## Folder Structure

Phase 1 currently introduces only documentation:

```text
ARGUS/
├── README.md
└── docs/
    ├── PROJECT_CONSTITUTION.md
    └── PHASE_1_FOUNDATIONS.md
```

We do not create `backend/` or `frontend/` yet because Phase 1 is about shared
understanding. This is deliberate. Professional teams often begin with design
documents before implementation.

## Files Created

### README.md

Purpose: Introduces the project and current phase.

Why it exists: GitHub visitors, recruiters, and future contributors need a fast
way to understand what ARGUS is.

How it fits: It is the front door of the repository.

### docs/PROJECT_CONSTITUTION.md

Purpose: Defines project identity, engineering standards, phases, and learning
rules.

Why it exists: It keeps implementation decisions aligned with the educational
and architectural goals.

How it fits: It acts like the project's operating manual.

### docs/PHASE_1_FOUNDATIONS.md

Purpose: Teaches the first layer of web engineering concepts.

Why it exists: FastAPI, React, PostgreSQL, and agents are easier to understand
when the underlying client-server model is clear.

How it fits: It prepares us for Phase 2, where we build the first real API.

## HTTP

### What It Is

HTTP means Hypertext Transfer Protocol. It is the protocol browsers and servers
use to communicate.

A protocol is an agreed set of rules. HTTP defines how a client asks for
something and how a server responds.

Example:

```text
Client:  GET /api/health
Server:  200 OK
Body:    {"status": "ok"}
```

### Why We Need It

ARGUS will have a React frontend and a FastAPI backend. The frontend and backend
need a standard way to talk to each other. HTTP gives us that standard.

### How It Works

An HTTP request usually contains:

- method
- path
- headers
- optional body

An HTTP response usually contains:

- status code
- headers
- optional body

Common methods:

- `GET`: read data
- `POST`: create or compute something
- `PUT`: replace something
- `PATCH`: partially update something
- `DELETE`: remove something

Common status codes:

- `200 OK`: success
- `201 Created`: resource created
- `400 Bad Request`: invalid input
- `404 Not Found`: resource does not exist
- `422 Unprocessable Entity`: validation failed
- `500 Internal Server Error`: server bug or unexpected failure

### Industry Usage

Almost every web system uses HTTP:

- trading dashboards
- banking portals
- SaaS dashboards
- mobile apps
- AI APIs
- internal company tools

### Common Mistakes

- Using `GET` for actions that modify data
- Returning `200 OK` even when something failed
- Sending inconsistent response shapes
- Putting secrets in URLs
- Ignoring validation errors

### Interview Questions

- What is the difference between `GET` and `POST`?
- What does a `404` mean?
- Why should APIs use consistent status codes?
- What is the difference between a request header and request body?

## REST APIs

### What It Is

REST is an architectural style for designing APIs around resources.

A resource is a meaningful thing in the system:

- stock analysis
- portfolio
- report
- watchlist
- user

Example:

```text
GET /api/portfolios
POST /api/portfolios
GET /api/reports/NVDA
```

### Why We Need It

REST gives ARGUS predictable API design. Predictability matters because the
frontend, backend, tests, and documentation all depend on stable contracts.

### How It Works

REST combines:

- nouns in URLs
- HTTP methods for actions
- JSON for data exchange
- status codes for outcomes

Example request:

```http
POST /api/analyze
Content-Type: application/json

{
  "ticker": "NVDA"
}
```

Example response:

```json
{
  "ticker": "NVDA",
  "summary": "NVIDIA shows strong momentum...",
  "risk_level": "medium"
}
```

### Alternatives

- GraphQL: useful when clients need flexible queries
- gRPC: useful for high-performance service-to-service communication
- WebSockets: useful for continuous real-time updates

For ARGUS v1, REST is appropriate because it is simple, common, easy to test,
and interview-friendly.

### Common Mistakes

- Designing endpoints around verbs instead of resources
- Returning raw database objects directly
- Changing response shapes without versioning or coordination
- Skipping request and response schemas

### Interview Questions

- What makes an API RESTful?
- Why is JSON commonly used in APIs?
- When would you choose GraphQL over REST?
- What does API contract mean?

## Frontend vs Backend

### What The Frontend Does

The frontend is the user-facing application. In ARGUS, it will be built with
React and TypeScript.

Responsibilities:

- render dashboards
- collect user input
- call backend APIs
- show loading and error states
- visualize data
- manage client-side interaction

### What The Backend Does

The backend owns business logic and trusted computation. In ARGUS, it will be
built with FastAPI.

Responsibilities:

- validate requests
- fetch market data
- compute metrics
- coordinate agents
- talk to databases
- call AI services
- return structured responses

### Why The Split Matters

If financial calculations live only in the browser, they are harder to secure,
test, and reuse. If all display logic lives in the backend, the user experience
becomes rigid.

The split lets each side do what it is good at.

### Common Mistakes

- Putting secrets in frontend code
- Duplicating business logic in frontend and backend
- Letting frontend and backend disagree about data shapes
- Treating the backend as a thin proxy with no real architecture

### Interview Questions

- What logic belongs on the frontend?
- What logic belongs on the backend?
- Why should API responses be typed?
- Why should secrets never be exposed to browser JavaScript?

## Relational Databases And PostgreSQL

### What A Relational Database Is

A relational database stores data in tables. Tables contain rows and columns.

Example:

```text
portfolios
id | name          | created_at
1  | AI Portfolio  | 2026-06-03

holdings
id | portfolio_id | ticker | weight
1  | 1            | NVDA   | 40
2  | 1            | MSFT   | 30
3  | 1            | AAPL   | 30
```

The relationship is:

```text
one portfolio has many holdings
```

### Why ARGUS Needs A Database

ARGUS eventually needs to remember:

- users
- portfolios
- watchlists
- generated reports
- uploaded documents
- agent runs
- analysis history

Without a database, every request is temporary.

### Why PostgreSQL

PostgreSQL is a production-grade open-source relational database. It supports:

- SQL
- indexes
- transactions
- foreign keys
- JSON columns
- full-text search
- strong consistency

### Core Concepts

Primary key: uniquely identifies a row.

Foreign key: links one table to another.

Index: speeds up lookups.

Transaction: groups operations so they succeed or fail together.

Normalization: organizing data to reduce duplication and inconsistency.

### Industry Usage

PostgreSQL is widely used in fintech, SaaS, analytics tools, internal platforms,
and AI products that need reliable structured data.

Bloomberg-like systems depend heavily on databases because financial research
requires durable, queryable, auditable information.

### Common Mistakes

- Storing everything as unstructured JSON
- Forgetting indexes on frequently queried fields
- Not using foreign keys
- Mixing database models with API response models
- Treating migrations as optional

### Interview Questions

- What is a primary key?
- What is a foreign key?
- Why do indexes speed up reads but slow down writes?
- What does ACID mean?
- Why use migrations?

## Async Programming

### What It Is

Async programming lets one program handle many waiting operations efficiently.

Waiting operations include:

- HTTP calls to market data providers
- database queries
- AI API requests
- file reads
- network calls

### Why ARGUS Needs It

ARGUS will often wait on external systems:

- yfinance
- Gemini
- PostgreSQL
- ChromaDB
- news APIs

While one request waits, the server should be able to work on other requests.

### How It Works

Synchronous style:

```python
price = fetch_price("NVDA")
news = fetch_news("NVDA")
analysis = call_llm(price, news)
```

Each line waits for the previous line.

Asynchronous style:

```python
price_task = fetch_price("NVDA")
news_task = fetch_news("NVDA")
price, news = await asyncio.gather(price_task, news_task)
```

Independent waiting tasks can make progress concurrently.

### Important Distinction

Async does not automatically make CPU-heavy work faster.

It helps most when the program spends time waiting on I/O.

For CPU-heavy quant workloads, we may eventually use worker processes,
background tasks, or vectorized libraries such as NumPy and pandas.

### Common Mistakes

- Using async syntax without async libraries
- Blocking the event loop with slow synchronous calls
- Forgetting `await`
- Running CPU-heavy work inside request handlers
- Assuming async means parallel CPU execution

### Interview Questions

- What is an event loop?
- What kind of tasks benefit from async?
- What is the difference between concurrency and parallelism?
- Why can blocking code hurt an async web server?
- What does `asyncio.gather()` do?

## Testing Instructions

For Phase 1, there is no application runtime yet. The test is documentation
review:

1. Read `README.md`.
2. Read `docs/PROJECT_CONSTITUTION.md`.
3. Read `docs/PHASE_1_FOUNDATIONS.md`.
4. Confirm that the Phase 1 concepts make sense before moving to Phase 2.

Later phases will add automated tests using `pytest`, frontend tests, and API
contract checks.

## Common Bugs

At this phase, the common bugs are conceptual:

- confusing API routes with frontend routes
- thinking FastAPI and React run in the same process
- assuming JSON is the database
- believing async automatically means faster computation
- starting with agents before deterministic services exist

## Knowledge Check

1. What problem does HTTP solve?
2. Why does ARGUS need a backend instead of calling all APIs from React?
3. What is an API contract?
4. Why do relational databases use tables?
5. What is the difference between concurrency and parallelism?
6. Why should quant metrics be computed deterministically instead of invented by
   an LLM?

## Next Steps

Phase 2 will create the first working MVP loop:

```text
ticker input -> FastAPI endpoint -> market data service -> structured response
```

Before Phase 2 implementation, we will introduce:

- FastAPI
- Pydantic validation
- route handlers
- service layers
- HTTP testing with `pytest`

