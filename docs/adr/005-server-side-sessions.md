# ADR 005: Server-side sessions instead of JWTs

## Status

Accepted (implemented in `app/services/auth.py`, `app/api/deps.py`).

## Context

ARGUS needs accounts so portfolios, research history, and documents are
private. The UI is served from the same origin as the API. Requirements:
immediate logout and revocation, no tokens readable by page JavaScript, and
simple operation without a key-management story.

## Decision

* Opaque 256-bit random tokens; only `SHA-256(token)` is stored in `sessions`.
* Browser delivery: `HttpOnly; SameSite=Lax` cookie (`Secure` behind HTTPS).
  API clients may use `Authorization: Bearer`.
* CSRF: cookie-authenticated mutations require the `X-ARGUS-CSRF: 1` header
  (cannot be set by cross-site forms; cross-origin scripts need a CORS
  preflight that only allow-listed origins pass).
* Argon2id password hashing with rehash-on-login; timing-equalized login;
  per-IP and per-email rate limits.

## Alternatives

* **JWT access + refresh tokens:** stateless verification, but revocation needs
  a denylist (which is server state anyway), and refresh-token rotation and
  storage add complexity. A single-origin app gains nothing from it.
* **Tokens in localStorage:** exposed to any XSS; rejected.

## Consequences

One database lookup per authenticated request (indexed primary key). Sessions
expire after `ARGUS_SESSION_TTL_HOURS`. Logout deletes the row immediately.
The in-memory rate limiter is per process.
