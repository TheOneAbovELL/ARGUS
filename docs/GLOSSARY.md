# ARGUS Glossary

## File Purpose

This glossary defines the core vocabulary used throughout ARGUS.

## Why It Exists

Large technical projects become easier when words have stable meanings. This is
especially important when learning full-stack engineering, finance, databases,
and AI systems at the same time.

## How It Fits Into The System

Future documentation, code comments, API specs, and interview notes can link
back to this glossary when a concept appears.

## Terms

### API

API means Application Programming Interface.

In ARGUS, an API is the contract that lets the frontend ask the backend for
data or actions.

Example:

```text
POST /api/analyze
```

### REST

REST is an API design style that uses HTTP methods and resource-oriented URLs.

Example:

```text
GET /api/portfolios
POST /api/portfolios
```

### HTTP

HTTP is the protocol browsers and servers use to exchange requests and
responses.

Example:

```text
Client sends: GET /api/health
Server returns: 200 OK
```

### JSON

JSON means JavaScript Object Notation.

It is a lightweight data format commonly used for API request and response
bodies.

Example:

```json
{
  "ticker": "NVDA"
}
```

### ORM

ORM means Object-Relational Mapper.

An ORM lets application code work with database rows using programming language
objects.

In ARGUS, SQLAlchemy will eventually map Python classes to PostgreSQL tables.

### Async

Async means asynchronous programming.

It lets a program efficiently handle waiting tasks such as API calls, database
queries, or network requests.

Async is about concurrency, not automatically about faster CPU computation.

### Coroutine

A coroutine is a function that can pause while waiting and resume later.

In Python, coroutines are commonly created with `async def` and paused with
`await`.

Example:

```python
async def fetch_market_data(ticker: str) -> dict:
    ...
```

### WebSocket

A WebSocket is a persistent two-way connection between client and server.

Unlike normal HTTP requests, a WebSocket can stay open so the server can push
updates to the browser.

ARGUS may use WebSockets later for live market updates and agent progress.

### Agent

An agent is a specialized software worker that performs a specific reasoning or
tool-using role.

In ARGUS, future agents may include:

- Market Agent
- News Agent
- Risk Agent
- Strategy Agent

An agent should not be magic. It should have clear inputs, tools, outputs, and
responsibilities.

### RAG

RAG means Retrieval-Augmented Generation.

It is a pattern where a system retrieves relevant documents or facts before
asking an LLM to generate an answer.

In ARGUS, RAG may help answer questions using annual reports, filings, research
notes, and internal analysis history.

### Embedding

An embedding is a numeric representation of text, images, or other data.

Texts with similar meanings should have embeddings that are close together in
vector space.

Embeddings help systems search by meaning instead of exact keywords.

### Vector Database

A vector database stores embeddings and supports similarity search.

In ARGUS, a vector database such as ChromaDB may help retrieve relevant
financial documents for RAG workflows.

## Common Beginner Mistakes

- using API, route, and endpoint as if they always mean the same thing
- thinking JSON is a database
- assuming async means parallel CPU execution
- treating agents as vague prompts instead of designed components
- using embeddings without understanding similarity search

## Future Improvements

This glossary should expand as ARGUS introduces:

- SQLAlchemy
- Alembic
- Redis
- Celery
- ChromaDB
- Sharpe Ratio
- beta
- drawdown
- WebSockets
- LangGraph

