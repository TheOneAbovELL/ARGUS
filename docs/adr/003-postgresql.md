# ADR 003: Use PostgreSQL For Durable Structured Data

## File Purpose

This Architecture Decision Record explains why ARGUS will use PostgreSQL as its
primary relational database.

## Why It Exists

ARGUS will eventually store portfolios, holdings, reports, watchlists, users,
agent runs, and research history. These are durable structured records, so the
database choice is foundational.

## How It Fits Into The System

PostgreSQL will sit behind the FastAPI backend. Application code will access it
through SQLAlchemy, and schema changes will be managed through Alembic
migrations in a later phase.

## Status

Accepted

## Context

ARGUS needs reliable storage for:

- user accounts
- portfolios
- holdings
- watchlists
- generated research reports
- uploaded document metadata
- agent execution history
- analysis audit trails

The database must support relationships, indexes, transactions, and reliable
querying.

## Decision

Use PostgreSQL as the primary database.

## Reason

PostgreSQL is appropriate because it provides:

- relational tables
- strong consistency
- ACID transactions
- foreign keys
- indexes
- joins
- JSON support when needed
- production maturity
- broad industry adoption

ARGUS is a financial research system. Financial systems need correctness,
durability, and queryability. PostgreSQL is a strong default for that.

## Alternatives

### SQLite

SQLite is excellent for local prototypes and tests. It is simple and requires
no server.

It is not the best long-term primary database for a multi-user research system
that needs concurrent access and production deployment.

### MongoDB

MongoDB is a document database. It is useful when records are flexible and do
not have many relational constraints.

ARGUS has strongly related entities such as users, portfolios, holdings, and
reports, so a relational database is a cleaner fit.

### JSON Files

JSON files are simple for tiny demos, but they quickly become painful.

They lack built-in indexing, relationships, transactions, concurrent access
control, and query language support.

## Tradeoffs

PostgreSQL advantages:

- reliable structured storage
- powerful querying
- strong data integrity
- production maturity
- good fit for financial records

PostgreSQL drawbacks:

- requires setup and connection management
- schema design matters
- migrations must be handled carefully
- indexes improve reads but add write overhead

## Industry Usage

PostgreSQL is used in:

- fintech products
- SaaS platforms
- analytics tools
- internal enterprise systems
- AI applications that need durable structured metadata

Institutional research systems rely heavily on relational databases because
financial data must be consistent, searchable, and auditable.

## Common Beginner Mistakes

- storing everything in one table
- avoiding foreign keys
- forgetting indexes on frequently queried columns
- using JSON columns for relational data
- changing schemas manually without migrations
- confusing database models with API schemas

## Interview Perspective

Possible interview question:

> Why PostgreSQL instead of JSON files?

Strong answer:

> ARGUS needs relationships, indexing, transactions, querying, and scalable
> concurrent access. JSON files are fine for tiny prototypes, but they become
> unreliable and hard to query as soon as portfolios, holdings, users, and
> reports need relationships.

## Future Improvements

Later phases will add:

- SQLAlchemy ORM models
- Alembic migrations
- indexes for common queries
- database tests
- possible read replicas at large scale

