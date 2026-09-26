# ARGUS Portfolio Analytics Engine

## Purpose

Portfolio analytics measures the combined behavior of allocations rather than
judging each security in isolation. ARGUS constructs a deterministic portfolio
return series from adjusted daily prices and passes the resulting value path to
the existing Quant Engine.

## Architecture

```text
POST /portfolio/analyze
    -> PortfolioService
        -> PortfolioEngine
            -> MarketDataProvider (all holdings and SPY concurrently)
            -> align histories by date
            -> construct weighted daily returns
            -> QuantEngine.compute_metrics
        -> PortfolioAnalysisResponse
```

## Portfolio construction convention

Input weights are percentages and must be positive, unique by ticker, and sum to
100. The engine converts them to fractions and models a daily-rebalanced,
long-only portfolio:

`portfolio return(t) = sum(weight(i) * asset return(i, t))`

The portfolio value begins at 1 and compounds each daily portfolio return. Daily
rebalancing keeps target weights constant. A buy-and-hold implementation would
allow weights to drift and would produce different results.

All holdings and SPY are aligned to their intersection of trading dates. Missing
dates are not fabricated or forward-filled.

## Portfolio return

ARGUS calculates CAGR from the constructed portfolio value series. Institutions
use portfolio return to evaluate the outcome of the allocation as a whole. CAGR
is sensitive to the analysis window and does not reveal the path of returns.

## Portfolio volatility

Portfolio volatility is the sample standard deviation of weighted daily returns,
annualized by the square root of 252. It naturally incorporates covariance:
assets that do not move together can reduce aggregate volatility. Historical
covariance can change sharply between market regimes.

## Portfolio Sharpe ratio

The Sharpe ratio is annualized mean daily excess portfolio return divided by its
daily volatility. It compares return earned with total risk taken. It can be
misleading for short histories, nonlinear payoffs, or non-normal returns.

## Portfolio beta

Portfolio beta is covariance between portfolio and SPY daily returns divided by
SPY return variance. Institutions use it to estimate systematic exposure and
size market hedges. Beta depends on the benchmark, frequency, and time window.

## Portfolio maximum drawdown

Maximum drawdown is the worst decline in portfolio value from a previous peak.
It captures realized loss severity and path dependency but does not measure
recovery time or forecast future losses.

## Diversification and correlation

Diversification is the reduction in aggregate risk created by combining imperfectly
correlated return streams. Correlation describes normalized co-movement, while
covariance also reflects scale. ARGUS does not average standalone volatilities;
it calculates volatility from the weighted portfolio return stream, so the
diversification effect is included directly in portfolio volatility and drawdown.

Adding more tickers does not guarantee diversification. Holdings concentrated in
the same factor, sector, or market regime may become highly correlated precisely
when protection is needed.

## Validation and failure behavior

- Empty portfolios: HTTP 422
- Duplicate normalized tickers: HTTP 422
- Negative, zero, or greater-than-100 individual weights: HTTP 422
- Weights not summing to 100: HTTP 422
- Invalid ticker syntax: HTTP 422
- Missing historical data: HTTP 404
- Upstream provider outage: HTTP 503

## Testing

Engine and API tests use deterministic dated histories. Tests verify exact metric
reuse, validation, response contracts, unknown tickers, and concurrent fetching.
Normal tests never call Yahoo Finance.

## Common bugs

- Averaging standalone metrics instead of constructing portfolio returns
- Ignoring covariance and correlation
- Combining returns from mismatched trading dates
- Mixing percentage weights with decimal weights
- Allowing duplicate tickers after normalization
- Assuming more holdings always means more diversification
- Forgetting that daily rebalancing differs from buy-and-hold
- Using unadjusted prices across corporate actions
- Silently filling unavailable history

## Interview preparation

### Recruiter questions

1. What user problem does the Portfolio Engine solve?
2. What makes this feature closer to an institutional platform?
3. How did you ensure the feature was reliable without depending on live tests?

### Quant questions

1. Why is portfolio volatility not the weighted average of asset volatilities?
2. How do covariance and correlation create diversification?
3. How does daily rebalancing differ from buy-and-hold construction?
4. Why must all security and benchmark returns be date-aligned?
5. How would concentrated factor exposure undermine ticker-level diversification?

### System design questions

1. Why does the Portfolio Engine orchestrate while the Quant Engine computes?
2. How does dependency injection allow deterministic provider fixtures?
3. How would you bound concurrency for a portfolio containing thousands of assets?
4. Where would caching fit later without changing metric formulas?
5. How does the provider abstraction isolate Yahoo Finance?

### Behavioral questions

1. Describe a design decision where you reused an existing component.
2. How did you resolve ambiguity around portfolio rebalancing conventions?
3. Describe how you prevented a network integration from making tests flaky.
4. What trade-off did you make between feature scope and extensibility?
