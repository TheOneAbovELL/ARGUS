# Research Engine: Agents, Evidence, and Validation

ARGUS produces research reports in which **every claim cites verifiable
evidence** and every number comes from the deterministic engine. Language-model
synthesis is optional, uses only free resources (a local model, or an explicitly
allowed free-tier endpoint such as Groq), and is held to the same validation
rules as the deterministic agents.

## Pipeline

`app/agents/coordinator.py` runs a fixed, bounded pipeline (no autonomous
loops, no model-initiated tool calls, at most one model call):

1. **Validate** the symbol and question (≤500 chars).
2. **Gather** concurrently: price history → quant metrics (required); quote,
   profile, news (optional).
3. **Retrieve** owner-scoped document passages (signed-in users who have
   indexed documents for the symbol): one query for the user's question, one
   default risk/guidance query.
4. **Build the evidence ledger** (`evidence.py`).
5. **Run specialist agents** (deterministic, read only from the ledger).
6. **Synthesize** with the local LLM if one is configured.
7. **Validate** every claim (`validation.py`); drop failures and log why.
8. **Assemble** the report with limitations, generation info, and a stage trace.

The trace (`step`, `status`, `duration_ms`, `detail`) is returned with every
report and streamed as Server-Sent Events by `POST /api/research/stream`.

## Evidence ledger

| Prefix | Kind | Source | Trusted? |
|---|---|---|---|
| `Q` | quote | provider quote with as-of time | data |
| `P` | profile | classification and provider-reported stats | data |
| `M` | metric | ARGUS quant engine (value + formatted statement) | computed |
| `N` | news | headline, publisher, date, URL | **untrusted** third-party text |
| `D` | document | retrieved passage with document id, page, chunk id, score | **untrusted** |
| `C` | method | ARGUS classification thresholds (e.g. beta > 1.20 = elevated) | methodology |

The conventions item (`C1`) exists so that interpretive thresholds are
themselves cited, rather than appearing as unexplained numbers.

## Agents

| Agent | Purpose | Inputs | Output | Never does |
|---|---|---|---|---|
| Market | Price, trend, benchmark-relative performance, volatility band | Q, P, M, C | `market` section | Recompute metrics |
| Risk | Beta, drawdown, VaR/CVaR, Sharpe; threshold-based risk flags | M, C | `risk` section + flags | Invent thresholds silently |
| News | Attributable headlines tagged to the symbol | N | `news` section | Score sentiment (unreliable from headlines) |
| Document | Verbatim, page-cited passages | D | `documents` and `answer` sections | Paraphrase documents in deterministic mode |
| Strategy | Bull / base / bear framing as labelled interpretations | M, flags, N, D | `scenarios` | Recommend trades, targets, or sizes |

Claims carry `kind: fact | interpretation` and `evidence_ids`.

## Validation rules (`app/agents/validation.py`)

A claim is rejected when it

1. cites an evidence id that does not exist;
2. is a `fact` with no citation;
3. contains a number that does not appear in its cited evidence after rounding
   to the claim's own precision (`48.7%` matches `48.68%`; `48.681%` and `52%` do
   not; `3.97T` matches `3,973,186,846,720` within 0.6%);
4. contains a date (ISO or month-name) or a bare year that is not in its cited evidence;
5. states a percentage in words, or writes a number in a form the extractor
   cannot verify (`x52%`, `.52`, `was_52%`);
6. is empty or longer than 700 characters;
7. gives investment advice outside a verbatim quotation (buy/sell, "strong buy",
   price targets, "upside of", "should buy", ...); "sell-off" and quoted headlines
   are not advice;
8. is a `fact` that relies **only** on third-party text (headlines, the user's
   documents) without quoting it verbatim or attributing it ("According to the
   10-K, ...", "Reuters reported ...");
9. binds a number to a named metric ("volatility was 35%", "beta is 1.20") and the
   number is not that metric's cited value; the methodology item (C1) and other
   metrics cannot support it, and a qualified label ("Benchmark total return")
   applies only if its qualifier is mentioned;
10. is an uncited interpretation, unless it only says the evidence is insufficient; or
11. (model output only) exceeds 12 claims in a section, duplicates another claim,
    or carries fields outside the schema. These are counted as rejections, not
    silently dropped.

Numbers are compared **with their sign**: an explicit +/- must match the signed
evidence value, and direction words ("fell", "lost", "drawdown", "below" are
negative; "rose", "gained", "outperformed" are positive) give unsigned numbers a
sign, so "fell 25.4%" cannot cite a +25.40% return. Every number is checked,
including whole numbers and `$` amounts. Both ends of ranges ("10-25%") are
checked. Month-name dates ("March 9, 2009") are checked like ISO dates.
Typographic dashes, minus signs, and non-breaking spaces are normalized first:
a real model emitted dates with U+2011 hyphens that would otherwise have
bypassed the date check.

**Trust levels.** Numbers in a claim's own words must come from trusted evidence
(ARGUS-computed metrics, quotes, provider profile data). Third-party text can
support only a quotation that appears verbatim in the cited item, or a claim that
attributes it to its source. So a document saying "volatility is 5%" can surface
only as "According to the 10-K, volatility is 5%", labelled as reported by a
third party, and never as an ARGUS fact. Sign words also include "negative",
"minus", "lower" and "worse", and text is NFKC-normalized first, so fullwidth or
small minus signs cannot flip a sign unnoticed.

Interpretations may draw conclusions, but they may not introduce numbers or
dates. Syntactic validity is not treated as support: a real id attached to the
wrong evidence still fails. Remaining known gaps: period descriptors ("over 5
years") are not compared with the analysis window; index names ("S&P 500") are
exempt; a number that is not directly attached to a metric name is matched
against any trusted number in its cited items.

## LLM policy

* Default `ARGUS_LLM_PROVIDER=none`: deterministic reports, zero cost.
* `openai_compatible` targets a local server (Ollama, LM Studio, llama.cpp) or,
  with `ARGUS_LLM_ALLOW_REMOTE=true`, a free-tier hosted endpoint. The
  development setup uses Groq's free tier (`openai/gpt-oss-120b`). Remote URLs
  are refused by default so a paid API cannot be used by accident, and no
  paid-provider SDK is a dependency.
* Free-tier budgets are respected rather than fought: on HTTP 429 the provider
  waits for the advertised reset (`retry-after` / `x-ratelimit-reset-tokens`)
  within the request's time budget, and otherwise reports "rate limited" and
  falls back. Prompts are compacted (sources printed once, findings that only
  restate an evidence item sent by reference) to fit more reports per minute.
* The model gets no tools. It returns a JSON Schema-constrained object.
* Prompt-injection defenses: documents and headlines are wrapped in
  `<untrusted_document>` / `<untrusted_headline>` elements, angle brackets in all
  third-party text (including text quoted inside agent findings) are
  neutralized, the system prompt says to report and never obey such text, and,
  most importantly, the validator rejects any claim whose numbers are not in
  cited evidence, so an obeyed injection cannot reach the user as a supported
  claim.
* Fallback (fail closed): model unavailable or timed out, malformed output,
  fewer than four accepted claims, or fewer than 60% of the model's claims
  accepted → deterministic report, with `generation.fallback_reason` and a stated
  limitation.
* Provenance in the report: every claim carries `origin` (`model` or `agent`).
  When the model leaves a section without valid claims, ARGUS shows its
  rule-based findings there, counts them in `validation.claims_backfilled` (not
  in the model's accepted count), and the UI marks them "rule-based". Validation
  removals are listed with reasons.

## Evaluation (`backend/evals/research_eval.py`)

`python -m evals.research_eval` runs four cases (with and without documents
and questions) across scenarios, scoring with deterministic assertions only:

| Scenario | What it exercises |
|---|---|
| deterministic | baseline grounding |
| faithful | scripted model reorganizing verified findings |
| hallucinating | scripted model adding a fabricated forecast, a fake citation, and an uncited "fact" |
| injected | document carries an override instruction; scripted model obeys it |
| outage / malformed | model failure handling |
| configured (opt-in) | the model configured in `backend/.env`, `--configured-llm` |

Metrics: schema compliance, citation validity, numeric fidelity (independent
re-validation), share of facts cited, metric fidelity (evidence equals the quant
engine), planted bad claims shown, validator rejections, fallback correctness,
consistency under fixed inputs, and latency.

**Offline run (scripted models, fixture data):** every scenario scored 1.00 on
citation validity, numeric fidelity, and facts cited; 0 planted claims were
shown (12 hallucinated and 4 injected claims were rejected); outage and
malformed scenarios fell back with a reason; deterministic and faithful runs
were consistent. These results show that the **validator and fallback
guarantees** hold, not a model's writing quality. `tests/test_evals.py` keeps
them as a regression gate.

**Real model runs (`--configured-llm`, Groq free tier, `openai/gpt-oss-120b`,
fixture data, 4 cases each, 2026-10-11).** These are small samples, reported
as measured:

| Run (code state) | LLM-synthesized | Model claims shown | Rejected by validator | Bad claims shown | Fallback causes |
|---|---|---|---|---|---|
| 1. first integration | 1 / 4 | 33 | 0 | 0 | 3 × rate limit (retry too short, ~6.6k-token prompt) |
| 2. reset-aware retry, compact prompt | 3 / 4 | 79 | 0 | 0 | 1 × `json_validate_failed` |
| 3. stricter validator | 1 / 4 | 23 | 0 | 0 | 2 × `json_validate_failed` after retry, 1 × rate limit |
| 4. json_object fallback mode (final) | 3 / 4 | 57 | 0 | 0 | 1 × rate limit (cases run back to back within one minute) |

Across every run, no planted or unsupported claim reached the user, and every
fallback produced a complete deterministic report with the reason shown.
Reports used about 4.8k–5.6k tokens each. An unthrottled report took 4–9 s;
averages are higher because requests wait out the free tier's 8,000
tokens-per-minute window.

What the runs exposed and what was changed:

* Strict server-side schema enforcement intermittently rejects the model's
  JSON, so a retry now uses `json_object` mode with the schema in the prompt.
  ARGUS validates the structure and every claim itself, so this does not
  weaken the guarantee.
* The model sometimes leaves sections empty. A real report came back with only
  6 claims. Empty sections now keep the deterministic agents' validated
  findings, and the report states which sections were filled.
* Real model text uses typographic hyphens in dates; the validator now
  normalizes them (see the validation rules above).
