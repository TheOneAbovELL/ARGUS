# ADR 002: Use React And TypeScript For The Frontend

## File Purpose

This Architecture Decision Record explains why ARGUS will use React with
TypeScript for the frontend.

## Why It Exists

The frontend is the user's research workspace. Choosing the right frontend stack
matters because ARGUS will eventually include dashboards, charts, watchlists,
portfolio views, agent activity, and real-time updates.

## How It Fits Into The System

React will render the terminal interface. TypeScript will help keep frontend
data shapes aligned with backend API contracts.

## Status

Accepted

## Context

ARGUS needs a frontend that can support:

- interactive dashboards
- reusable UI components
- typed API responses
- live data updates
- charting and data visualization
- complex state over time

The frontend should be resume-worthy and familiar to modern software teams.

## Decision

Use React with TypeScript, built with Vite.

## Reason

React is appropriate because it provides:

- component-based UI architecture
- a large ecosystem
- strong hiring-market relevance
- good support for dashboards and interactive tools
- compatibility with many charting and state-management libraries

TypeScript is appropriate because it adds static types to JavaScript. This helps
catch mistakes before runtime and makes API contracts clearer.

Vite is appropriate because it gives a fast development server and a simple
modern frontend build setup.

## Alternatives

### Vue

Vue is approachable and excellent for many dashboards. React has broader
industry usage in many internship and software engineering contexts.

### Svelte

Svelte is elegant and fast, but its ecosystem is smaller than React's.

### Next.js

Next.js is powerful for full-stack React applications and server-side rendering.
ARGUS initially does not need server-rendered marketing pages. A Vite React app
keeps the architecture simpler and makes the frontend/backend boundary clearer.

### Plain HTML, CSS, And JavaScript

This is useful for small demos but becomes difficult to maintain when building
complex dashboards with reusable components and typed data.

## Tradeoffs

React advantages:

- broad ecosystem
- reusable component model
- strong hiring relevance
- excellent dashboard support

React drawbacks:

- state management can become messy without discipline
- performance requires care in large interfaces
- beginners may overuse components or hooks

TypeScript advantages:

- catches type mismatches early
- documents data shapes
- improves refactoring safety

TypeScript drawbacks:

- adds learning overhead
- can become noisy if types are over-engineered

## Industry Usage

React and TypeScript are widely used in:

- fintech dashboards
- SaaS applications
- internal analytics platforms
- trading tools
- AI product interfaces

Many professional dashboards use component-based frontend systems similar to
what ARGUS will build.

## Common Beginner Mistakes

- storing all state in one giant component
- duplicating backend logic in frontend code
- ignoring loading and error states
- using `any` everywhere in TypeScript
- building UI before defining API response shapes

## Interview Perspective

Possible interview question:

> Why use TypeScript instead of plain JavaScript?

Strong answer:

> ARGUS depends on structured API responses for financial data. TypeScript helps
> enforce those shapes in the frontend, catches mistakes earlier, and makes the
> codebase safer to refactor as the dashboard grows.

## Future Improvements

Revisit frontend architecture when ARGUS needs:

- advanced client-side caching
- more complex global state
- route-level data loading
- real-time streaming dashboards
- authenticated user sessions

