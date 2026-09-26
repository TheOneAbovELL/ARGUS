# ARGUS Intelligence Engine

## Purpose

The Intelligence Engine converts grounded market data, deterministic analytics,
and provider-supplied headlines into an explainable research brief. It is not a
chatbot and does not invent facts. Every conclusion is traceable to a metric,
threshold, or headline supplied by an existing ARGUS component.

No language model, database, RAG system, or autonomous tool loop is introduced in
this phase. The typed agent boundaries allow a future synthesizer to be injected
without replacing the Quant Engine or weakening deterministic tests.

## Architecture

```text
POST /research
    -> ResearchCoordinator
        +-> MarketDataService -> QuantEngine
        +-> NewsAgent -> company and SPY news
              |
              +-> MarketAgent
              +-> RiskAgent
                    |
                    +-> StrategyAgent
    -> ResearchResponse
```

The diagram represents dependencies, not a claim that every task can start at
once. Quant analysis and news retrieval run concurrently. Once analysis exists,
Market and Risk Agents run concurrently. Strategy runs last because it consumes
all three specialist outputs.

## Agent responsibilities

### Market Agent

Consumes the normalized company snapshot and Quant Metrics. It classifies the
historical annual-return trend and volatility band, then reports the exact price,
return, and volatility values used. It does not fetch data or recalculate metrics.

### Risk Agent

Consumes beta, Sharpe ratio, volatility, and maximum drawdown. It applies explicit
thresholds to flag above-market sensitivity, high realized volatility, material
drawdowns, and negative risk-adjusted performance. Thresholds are interpretations,
not predictions or investment recommendations.

### News Agent

Fetches recent company and SPY headlines concurrently through the provider
abstraction. It produces an extractive digest with publisher attribution. It does
not infer facts absent from headlines, scrape arbitrary pages, or fabricate a
sentiment score.

### Strategy Agent

Consumes Market, Risk, and News outputs and produces balanced bull, bear, and
neutral scenarios plus key risks and opportunities. Scenarios describe what the
current evidence can support; they are not trade instructions or forecasts.

### Research Coordinator

Owns the execution graph, concurrency, error translation, and final aggregation.
Agents remain small because the coordinator—not the route—controls dependencies.

## API

`POST /research`

```json
{
  "ticker": "NVDA"
}
```

The response contains market, risk, and news summaries; bull, bear, and neutral
cases; and explicit risk and opportunity lists. Ticker validation is identical to
`POST /analyze`.

## Explainability and reliability

- Finance metrics come only from the deterministic Quant Engine.
- News comes only from normalized provider records.
- Agent thresholds are visible in code and stable under test.
- Identical inputs produce identical outputs.
- Provider work remains async-friendly through the existing adapter.
- Missing tickers return 404; upstream failures return 503.

## Testing

Tests inject fixed analytics, headlines, and agent outputs. They verify specialist
behavior, threshold flags, scenario grounding, coordinator dependency ordering,
concurrency, API shape, validation, and yfinance news normalization. The normal
suite does not make live network requests.

## Common mistakes

- Calling every class an agent without giving it one clear responsibility
- Running dependent tasks concurrently before their inputs exist
- Letting agents recalculate or alter deterministic metrics
- Treating a headline as verified article content
- Hiding the rules that produced a risk label
- Returning only a bullish narrative and omitting counter-evidence
- Coupling routes directly to providers or specialist agents
- Confusing scenario generation with financial advice

## Knowledge check

1. Why does Strategy run after the three specialist outputs exist?
2. Why should RiskAgent interpret metrics instead of calculating them?
3. What makes an extractive news digest safer than invented summarization?
4. Which coordinator tasks can genuinely run concurrently?
5. How could a language-model synthesizer be added without changing analytics?
6. Why are bull, bear, and neutral cases preferable to one directional answer?
