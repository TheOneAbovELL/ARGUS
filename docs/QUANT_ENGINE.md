# Quant Engine and Portfolio Engine

All financial numbers in ARGUS come from the pure functions in `app/quant/` and
`app/portfolio/`. No language model computes, estimates, or rewrites a metric.

## Data conventions

* **Prices:** dividend-adjusted closes (`adj_close`) for every return metric;
  traded closes (`close`, split-adjusted by the provider) are returned for charts.
* **Returns:** simple close-to-close returns `p_t / p_{t-1} - 1`.
* **Annualization factor N:** inferred from observation density: 365 when the
  series has more than ~308 observations per 365.25 calendar days (daily trading,
  e.g. crypto), otherwise 252. Density is used instead of counting Saturdays and
  Sundays, so exchanges with a Friday-Saturday weekend (e.g. Sun-Thu sessions)
  still get 252.
* **Alignment:** relative metrics use the inner join of asset and benchmark
  dates. Prices are never forward-filled (that would fabricate zero returns).
* **Risk-free rate:** annual decimal (default 0), converted to a per-period rate
  `(1 + rf)^(1/N) - 1`.
* **Signs:** drawdown, VaR, and CVaR are returns, so losses are negative.
* **Undefined is `null`, never `0`.** A metric that is undefined for the input
  (zero volatility, no downside, too few observations) is reported as `null`
  with a warning, and the other metrics are still returned. Dispersion below
  `1e-12` counts as zero: without that guard, floating-point noise on a constant
  return series produced a Sharpe ratio of about 10¹⁵ (found and fixed by a test).
* **Short samples:** fewer than 60 returns adds an "unreliable" warning.
* **Data cleaning:** duplicate dates keep the latest bar; missing,
  non-positive, or non-finite closes are dropped; both are reported as quality notes.

## Metric definitions

The same definitions are served at `GET /api/meta/metrics` for UI tooltips.

| Metric | Definition |
|---|---|
| Total return | `P_end / P_start − 1` |
| Annualized return (CAGR) | `(P_end / P_start)^(365.25 / calendar days) − 1` (calendar-based, robust to gaps) |
| Volatility | sample stdev of returns × √N |
| Sharpe | mean(r − rf) / stdev(r − rf) × √N |
| Sortino | mean(r − rf) / downside deviation × √N; downside deviation = √(mean(min(r − rf, 0)²)) over all periods |
| Max drawdown | min over t of `P_t / max_{s≤t} P_s − 1`, with peak, trough, and recovery dates |
| Longest drawdown | longest run of observations below a prior peak (including an unrecovered one) |
| VaR 95% (1-day, historical) | 5th percentile of daily returns, linear interpolation; ≥20 returns required |
| CVaR 95% | mean of returns at or below the VaR |
| Beta / alpha | OLS of asset excess returns on benchmark excess returns; alpha = intercept × N (arithmetic) |
| Correlation, R² | Pearson on aligned daily returns; R² = ρ² |
| Tracking error / IR | stdev(r_a − r_b) × √N; IR = mean(r_a − r_b) × N / TE |
| Rolling volatility / beta | 63-observation trailing windows, `null` until the window fills |

## Portfolio models

| Model | NAV | When it applies |
|---|---|---|
| `daily_rebalanced` | `NAV_t = NAV_{t−1} · (1 + Σ w_i r_{i,t})` | Weights reset to target every close |
| `buy_and_hold` | `NAV_t = Σ w_i · P_{i,t} / P_{i,0}` | Allocate once; weights drift (ending weights reported) |

Averaging constituent returns is only valid for the rebalanced model, and the
engine never does it for buy-and-hold. Assets are inner-joined on common dates.
If a holding listed late, the window starts later and a warning says so. Mixed
currencies are flagged (no FX conversion).

**Risk decomposition (Euler):** with annualized covariance Σ and weights w,
σ_p = √(wᵀΣw); marginal risk = (Σw)/σ_p; contribution share =
w_i (Σw)_i / σ_p², which sums to exactly 1. Diversification ratio =
Σ w_i σ_i / σ_p.

**Return contribution:** exact for buy-and-hold (`w_i × asset total return`,
sums to the portfolio total return); an arithmetic approximation for the
rebalanced model (stated in the response).

**Historical stress replay:** current weights are held through five named
episodes (GFC 2007–09, 2011 downgrade, Q4 2018, COVID 2020, 2022 rates).
An episode is reported as *not computable* when any holding lacks history
covering the episode (within 7 days of its start **and** end), rather than
silently re-weighting the remaining holdings or shortening the episode. The
benchmark return is measured over exactly the portfolio's first and last
replayed dates, so the two are comparable.

**Stated assumptions (returned with every analysis):** dividends reinvested; no
costs, taxes, slippage, or cash drag; no forward-fill; current weights applied
retrospectively (survivorship and look-ahead bias); no FX conversion.

## Validation approach

Tests use hand-computed fixtures and independent re-implementations (numpy)
rather than calling the code under test to produce expected values:
`tests/test_quant_*.py` and `tests/test_portfolio_engine.py`. They also check
invariants: drawdown ≤ 0 and equal to the running-peak definition;
correlation in [−1, 1] with a symmetric matrix and unit diagonal; risk
contributions sum to 1; buy-and-hold contributions sum to total return; a
single-asset portfolio equals the asset; invalid weights are rejected; and
missing history is an error, not a silent re-weight.

Out of scope (deliberately): optimizers and strategy backtests. They are easy to
add and hard to validate honestly without transaction-cost and survivorship
modelling.
