# ADR 007: Market-data provenance, caching, and failure semantics

## Status

Accepted (implemented in `app/providers/`).

## Context

The only free broad-coverage source available is Yahoo Finance via the
unofficial `yfinance` library: no SLA, rate limits, delayed quotes. The
original adapter had no timeouts or caching, converted any failure into either
an exception or "no data" inconsistently, and accepted only alphanumeric
tickers. During live testing we also found that yfinance, by default, swallows
transport errors and returns an empty frame, so an outage looked like
"symbol not found". Its shared HTTP session also hung under concurrent use.

## Decision

* **Provenance on every payload** (`provider`, `mode`, `retrieved_at`,
  `as_of`, `cached`, `stale`), where `mode` is `delayed`, `end_of_day`, or
  `fixture`. Never labelled real-time.
* **Explicit semantics:** `None` means the provider answered with no data;
  typed errors (`provider_unavailable`, `provider_rate_limited`,
  `provider_timeout`) mean it could not answer. yfinance is configured to raise,
  and a "missing" signal must repeat before it counts as not-found.
* **Caching decorator:** per-kind TTLs, long TTL for closed historical windows,
  short negative caching, single-flight, LRU bound, and stale-on-error only for
  real payloads (an outage is never turned into "not found").
* **Execution policy:** serialized yfinance calls, a per-attempt HTTP timeout, a
  shared overall deadline that abandoned workers observe, and bounded
  exponential backoff with jitter.
* **Fixture provider:** deterministic synthetic factor-model series, clearly
  labelled, for offline development and tests.

## Consequences

Repeated views are fast (cached analytics measured at about 10 ms against
about 3.5 s cold on live data). Under a slow network, long histories can time
out, and that is reported honestly as a 504. Caches are per process.
