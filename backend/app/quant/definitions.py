"""Human-readable definitions of every metric ARGUS reports.

Served at ``GET /api/meta/metrics`` so the UI can explain each number with
the exact convention the engine uses (kept next to the code that implements
them so the two do not drift).
"""

METRIC_DEFINITIONS: list[dict[str, str]] = [
    {
        "key": "total_return",
        "label": "Total return",
        "unit": "percent",
        "formula": "P_end / P_start - 1 on dividend-adjusted closes",
        "notes": "Includes reinvested dividends. Not annualized.",
    },
    {
        "key": "annualized_return",
        "label": "Annualized return (CAGR)",
        "unit": "percent",
        "formula": "(P_end / P_start) ^ (365.25 / calendar days) - 1",
        "notes": "Uses elapsed calendar time, so missing observations do not distort it. "
        "Annualizing short windows exaggerates noise.",
    },
    {
        "key": "annualized_volatility",
        "label": "Annualized volatility",
        "unit": "percent",
        "formula": "sample stdev of simple daily returns x sqrt(N)",
        "notes": "N = 252 for exchange calendars, 365 for assets that trade on weekends.",
    },
    {
        "key": "sharpe_ratio",
        "label": "Sharpe ratio",
        "unit": "ratio",
        "formula": "mean(r - rf_d) / stdev(r - rf_d) x sqrt(N)",
        "notes": "rf_d = (1 + rf_annual)^(1/N) - 1. Undefined (null) when volatility is zero.",
    },
    {
        "key": "sortino_ratio",
        "label": "Sortino ratio",
        "unit": "ratio",
        "formula": "mean(r - rf_d) / downside deviation x sqrt(N)",
        "notes": "Downside deviation = sqrt(mean(min(r - rf_d, 0)^2)) over all periods. "
        "Undefined when no return falls below the target.",
    },
    {
        "key": "max_drawdown",
        "label": "Maximum drawdown",
        "unit": "percent",
        "formula": "min_t (P_t / max_{s<=t} P_s - 1)",
        "notes": "Reported as a negative number with its peak, trough, and recovery dates.",
    },
    {
        "key": "longest_drawdown_days",
        "label": "Longest drawdown",
        "unit": "periods",
        "formula": "max over drawdowns of (index where the prior peak is regained, or the last index) - (index of that peak)",
        "notes": "Measured in observations (trading days for exchange-listed assets), from the peak until the price first regains it; an unrecovered drawdown counts to the end of the window.",
    },
    {
        "key": "var_95",
        "label": "1-day historical VaR (95%)",
        "unit": "percent",
        "formula": "5th percentile of daily returns (linear interpolation)",
        "notes": "Expressed as a return (negative = loss). No normality assumption. "
        "Requires at least 20 returns.",
    },
    {
        "key": "cvar_95",
        "label": "1-day expected shortfall (95%)",
        "unit": "percent",
        "formula": "mean of daily returns at or below the 95% VaR",
        "notes": "Average loss on the worst 5% of days.",
    },
    {
        "key": "beta",
        "label": "Beta",
        "unit": "ratio",
        "formula": "cov(r_a - rf, r_b - rf) / var(r_b - rf)",
        "notes": "OLS slope on daily excess returns over dates both series traded.",
    },
    {
        "key": "alpha",
        "label": "Alpha (Jensen, annualized)",
        "unit": "percent",
        "formula": "(mean(r_a - rf) - beta x mean(r_b - rf)) x N",
        "notes": "Arithmetic annualization of the daily regression intercept.",
    },
    {
        "key": "correlation",
        "label": "Correlation",
        "unit": "ratio",
        "formula": "Pearson correlation of daily returns",
        "notes": "Bounded in [-1, 1]; undefined for a constant series.",
    },
    {
        "key": "tracking_error",
        "label": "Tracking error",
        "unit": "percent",
        "formula": "stdev(r_a - r_b) x sqrt(N)",
        "notes": "Volatility of active returns versus the benchmark.",
    },
    {
        "key": "information_ratio",
        "label": "Information ratio",
        "unit": "ratio",
        "formula": "mean(r_a - r_b) x N / tracking error",
        "notes": "Undefined when tracking error is zero.",
    },
    {
        "key": "risk_contribution",
        "label": "Risk contribution",
        "unit": "percent",
        "formula": "w_i x (Sigma w)_i / (w' Sigma w)",
        "notes": "Euler decomposition of portfolio volatility; contributions sum to 100%.",
    },
    {
        "key": "diversification_ratio",
        "label": "Diversification ratio",
        "unit": "ratio",
        "formula": "sum(w_i x sigma_i) / sigma_portfolio",
        "notes": "1.0 means no diversification benefit; higher is more diversified.",
    },
]
