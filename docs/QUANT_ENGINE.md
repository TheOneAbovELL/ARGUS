# ARGUS Quant Analytics Engine

## Purpose

The Quant Engine converts adjusted daily closing prices into deterministic risk
and return analytics. It contains no AI, predictions, or hardcoded market
results. Identical inputs and configuration produce identical outputs.

## Architecture

```text
POST /analyze
    -> MarketDataService
        -> QuantEngine
            -> MarketDataProvider (asset and SPY history concurrently)
            -> metric functions
        -> AnalyzeResponse
```

The provider adapts Yahoo Finance data into dated price observations. The engine
aligns the asset and benchmark on shared trading dates before calculating daily
simple returns. Metric modules are pure functions, making the financial logic
independent from HTTP, yfinance, and dependency injection.

## Calculation conventions

- Prices: adjusted daily closes (`auto_adjust=True`)
- Window: one year by default (`ARGUS_QUANT_HISTORY_PERIOD`)
- Annualization: 252 trading days
- Benchmark: SPY by default (`ARGUS_QUANT_BENCHMARK_TICKER`)
- Risk-free rate: 0 by default (`ARGUS_QUANT_ANNUAL_RISK_FREE_RATE`)
- Missing or insufficient observations: explicit error; never estimated

## Metrics

### Annual return

Formula: `(ending price / starting price)^(252 / observed intervals) - 1`.

This is the compound annual growth rate implied by the observed price path.
Institutions use annualized return to compare investments measured over different
windows. It ignores the path between endpoints and is sensitive to the selected
start and end dates.

### Volatility

Formula: `sample standard deviation(daily returns) * sqrt(252)`.

Volatility measures dispersion, not direction. Risk teams use it in limits,
portfolio construction, scenario design, and risk-adjusted comparisons. It treats
upside and downside variation equally and historical volatility may not describe
future regimes.

### Sharpe ratio

Formula: `mean(daily return - daily risk-free rate) / sample standard deviation`
multiplied by `sqrt(252)`.

The Sharpe ratio measures excess return per unit of total volatility. Asset
managers use it to compare risk-adjusted performance. It is unstable for short
samples, assumes volatility is an adequate risk proxy, and can be distorted by
non-normal or smoothed returns.

### Maximum drawdown

Formula: the minimum value of `price / running peak - 1`.

Maximum drawdown is the worst historical peak-to-trough loss. Institutions use it
for capital preservation limits, manager evaluation, and stress discussions. It
describes one realized path and does not state how long recovery takes or predict
the next loss.

### Beta versus the S&P 500

Formula: `sample covariance(asset returns, benchmark returns) / sample variance`
of benchmark returns.

Beta estimates sensitivity to broad-market movement. A beta above one indicates
greater historical sensitivity; below one indicates lower sensitivity. Portfolio
and risk teams use beta for hedging and systematic-risk attribution. It depends on
the benchmark, data frequency, date alignment, and sample window, and it can
change across regimes.

## Reliability and testing

Asset and benchmark histories are requested concurrently. Both histories are
aligned by date before returns are calculated, preventing holiday or missing-row
mismatches. Pure metric tests use fixed arrays. Engine and API tests inject
deterministic providers, so the normal suite never depends on Yahoo Finance.

## Common implementation errors

- Using unadjusted closes across splits or dividends
- Comparing asset and benchmark returns from different dates
- Mixing population and sample standard deviations
- Annualizing returns or volatility twice
- Using 365 instead of a documented trading-day convention
- Silently replacing missing observations or undefined ratios
- Treating volatility as equivalent to loss
- Blocking the event loop with synchronous market-data calls

## Interview preparation

### Sharpe ratio

1. Why must the risk-free rate match the return frequency?
2. What makes a Sharpe ratio unreliable for short or non-normal return series?
3. Why is Sharpe undefined for a constant return stream in this implementation?

### Beta

1. Why must asset and benchmark dates be aligned before computing beta?
2. How does benchmark choice alter beta?
3. What does a negative beta mean, and why might it be unstable?

### Volatility

1. Why is daily volatility multiplied by the square root of 252?
2. Why does ARGUS use sample rather than population standard deviation?
3. Why does volatility penalize upside and downside movement equally?

### Maximum drawdown

1. How is maximum drawdown different from volatility?
2. Why is drawdown path-dependent?
3. What information does maximum drawdown omit about recovery?

### Quant Engine architecture

1. Why are metric calculations pure functions?
2. Why does the engine, rather than the route, fetch benchmark history?
3. Where should calculation conventions be configured and documented?

### Service layer and dependency injection

1. What responsibility does `MarketDataService` retain?
2. How does provider injection keep tests deterministic?
3. How could ARGUS replace Yahoo Finance without rewriting metric functions?
