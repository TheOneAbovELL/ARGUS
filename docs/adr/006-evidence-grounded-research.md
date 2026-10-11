# ADR 006: Evidence ledger, deterministic agents, and validated optional LLM synthesis

## Status

Accepted (implemented in `app/agents/`).

## Context

The original agents formatted metrics into template strings and pasted raw
document text; claims had no link to their sources. The project goal is
research whose every statement can be traced and checked. The owner also
requires that **no paid AI API** be used.

## Decision

1. Build an **evidence ledger** before any synthesis: each metric, quote,
   profile stat, headline, document passage, and methodology threshold gets an
   id and a canonical statement.
2. **Deterministic specialist agents** (market, risk, news, document,
   strategy) emit claims (`fact` or `interpretation`) that cite ledger ids.
3. **Optional synthesis** by a local model (or an explicitly allowed free-tier
   endpoint) through a narrow
   `generate_json(system, user, schema)` interface, with no tools and a JSON
   Schema-constrained output. Remote endpoints are refused by default.
4. A **validator** gates every claim from either source: citations must exist,
   facts must cite, and numbers and dates must appear in the cited evidence.
5. A **fixed pipeline** instead of an agent loop or LangGraph: inputs are known,
   so model-driven tool selection would add cost and failure modes without
   adding information.

## Alternatives

* *LLM writes the whole report from raw data:* fluent, but unverifiable, and
  numbers drift.
* *LangGraph / autonomous tool use:* useful for open-ended tasks; unnecessary
  here and harder to bound.
* *Model-graded faithfulness:* kept out of the gate. Deterministic checks are
  reproducible and cannot be persuaded.

## Consequences

Reports are reproducible under fixed inputs and every number is traceable.
Without a model, prose is templated and answers to free-form questions are
extractive (relevant passages), and the report says so. The numeric check
skips years and small bare integers, a known gap.
