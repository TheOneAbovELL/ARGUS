"""Portfolio construction and analytics (pure computation, no I/O).

Two explicitly different portfolio models are supported:

``daily_rebalanced``
    Weights are reset to target at every close, so the portfolio return on day
    ``t`` is exactly ``sum_i w_i * r_{i,t}``.

``buy_and_hold``
    Capital is allocated once at the first shared close and positions then
    drift with prices. The NAV is ``sum_i w_i * P_{i,t} / P_{i,0}``; averaging
    constituent returns would be wrong for this model.

Both use dividend-adjusted closes (dividends reinvested in the same asset)
and ignore transaction costs, taxes, slippage, and FX conversion. Assets are
inner-joined on common trading dates; prices are never forward-filled.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

import numpy as np

from app.providers.models import PriceHistory
from app.quant.drawdown import drawdown_series
from app.quant.metrics import (
    PerformanceMetrics,
    QuantDataError,
    RelativeMetrics,
    performance_metrics,
    relative_metrics,
)
from app.quant.returns import (
    calendar_annualized_return,
    cumulative_returns,
    infer_periods_per_year,
    is_effectively_zero,
)
from app.quant.series import align_on_common_dates

WEIGHT_TOLERANCE = 1e-6
# An asset must have history within a week of an episode start to be replayed.
_EPISODE_GRACE = timedelta(days=7)


class RebalancingModel(StrEnum):
    DAILY_REBALANCED = "daily_rebalanced"
    BUY_AND_HOLD = "buy_and_hold"


@dataclass(frozen=True)
class PortfolioPosition:
    """A normalized allocation expressed as a fraction of capital."""

    ticker: str
    weight: float


class PortfolioValidationError(ValueError):
    """Raised when allocations violate portfolio invariants."""


@dataclass(frozen=True)
class AssetContribution:
    symbol: str
    weight: float
    ending_weight: float
    total_return: float
    annualized_return: float | None
    annualized_volatility: float | None
    beta: float | None
    return_contribution: float
    risk_contribution: float | None  # share of portfolio volatility (sums to 1)
    marginal_risk: float | None


@dataclass(frozen=True)
class PortfolioSeries:
    dates: tuple[date, ...]
    cumulative_return: tuple[float, ...]
    drawdown: tuple[float, ...]
    benchmark_dates: tuple[date, ...]
    benchmark_cumulative_return: tuple[float, ...]
    portfolio_cumulative_on_benchmark_dates: tuple[float, ...]


@dataclass(frozen=True)
class PortfolioAnalysis:
    model: RebalancingModel
    holdings: tuple[PortfolioPosition, ...]
    start: date
    end: date
    periods_per_year: int
    performance: PerformanceMetrics
    relative: RelativeMetrics | None
    assets: tuple[AssetContribution, ...]
    correlation_symbols: tuple[str, ...]
    correlation: tuple[tuple[float | None, ...], ...]
    diversification_ratio: float | None
    contribution_method: str
    series: PortfolioSeries
    warnings: tuple[str, ...]
    assumptions: tuple[str, ...]


ASSUMPTIONS = (
    "Dividend-adjusted closes are used; dividends are reinvested in the paying asset.",
    "No transaction costs, taxes, slippage, borrowing, or cash drag are modelled.",
    "Assets are aligned on dates when every holding traded; prices are never forward-filled.",
    "Weights are applied to the current holdings over the whole window, which introduces "
    "survivorship and look-ahead bias: the allocation was chosen with today's knowledge.",
    "Prices are not converted between currencies.",
    "Risk contributions use the sample covariance of daily returns and the target weights.",
)


def validate_holdings(holdings: Sequence[PortfolioPosition]) -> None:
    if not holdings:
        raise PortfolioValidationError("A portfolio must contain at least one holding.")
    if len(holdings) > 30:
        raise PortfolioValidationError("A portfolio can contain at most 30 holdings.")
    tickers = [holding.ticker for holding in holdings]
    if len(tickers) != len(set(tickers)):
        raise PortfolioValidationError("Duplicate ticker symbols are not allowed.")
    if any(
        not holding.ticker or not math.isfinite(holding.weight) or holding.weight <= 0
        for holding in holdings
    ):
        raise PortfolioValidationError("Every holding requires a ticker and a positive finite weight.")
    if not math.isclose(
        sum(holding.weight for holding in holdings), 1.0, rel_tol=0.0, abs_tol=WEIGHT_TOLERANCE
    ):
        raise PortfolioValidationError("Portfolio weights must sum to 100 percent.")


def portfolio_nav(
    prices: np.ndarray, weights: np.ndarray, model: RebalancingModel
) -> tuple[np.ndarray, np.ndarray]:
    """Return (NAV starting at 1.0, ending weights) for a T x N price matrix."""
    if model is RebalancingModel.DAILY_REBALANCED:
        returns = prices[1:] / prices[:-1] - 1.0
        nav = np.concatenate(([1.0], np.cumprod(1.0 + returns @ weights)))
        return nav, weights.copy()
    values = weights * prices / prices[0]
    nav = values.sum(axis=1)
    return nav, values[-1] / nav[-1]


def analyze_portfolio(
    holdings: Sequence[PortfolioPosition],
    histories: Mapping[str, PriceHistory],
    benchmark: PriceHistory | None,
    benchmark_symbol: str,
    model: RebalancingModel,
    annual_risk_free_rate: float,
    requested_start: date | None = None,
) -> PortfolioAnalysis:
    validate_holdings(holdings)
    symbols = [h.ticker for h in holdings]
    missing = [s for s in symbols if s not in histories]
    if missing:
        raise QuantDataError(f"Historical market data is unavailable for: {', '.join(missing)}.")

    warnings: list[str] = []
    for symbol in symbols:
        warnings.extend(f"{symbol}: {note}" for note in histories[symbol].quality_notes)

    dates, aligned = align_on_common_dates({s: histories[s].adjusted_closes() for s in symbols})
    if len(dates) < 3:
        raise QuantDataError("The holdings share fewer than three common trading dates in this window.")
    if requested_start is not None:
        latest_start = max(histories[s].start for s in symbols)
        if (latest_start - requested_start).days > 10:
            limiting = [s for s in symbols if histories[s].start == latest_start]
            warnings.append(
                f"The analysis starts on {dates[0].isoformat()} rather than "
                f"{requested_start.isoformat()} because {', '.join(limiting)} has no earlier history."
            )
    currencies = {histories[s].currency for s in symbols if histories[s].currency}
    if len(currencies) > 1:
        warnings.append(
            f"Holdings are priced in multiple currencies ({', '.join(sorted(currencies))}); "
            "values are combined without FX conversion."
        )

    weights = np.array([h.weight for h in holdings], dtype=float)
    prices = np.array([aligned[s] for s in symbols], dtype=float).T  # T x N
    nav, ending_weights = portfolio_nav(prices, weights, model)
    periods = infer_periods_per_year(dates)
    performance, perf_warnings = performance_metrics(dates, nav.tolist(), annual_risk_free_rate, periods)
    warnings.extend(perf_warnings)

    asset_returns = prices[1:] / prices[:-1] - 1.0
    cov = np.cov(asset_returns, rowvar=False, ddof=1).reshape(len(symbols), len(symbols)) * periods
    portfolio_var = float(weights @ cov @ weights)
    portfolio_vol = math.sqrt(portfolio_var) if portfolio_var > 0 else 0.0
    if is_effectively_zero(portfolio_vol / math.sqrt(periods)):
        portfolio_vol = 0.0
    asset_vols = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    if portfolio_vol > 0:
        marginal = cov @ weights / portfolio_vol
        risk_share = weights * marginal / portfolio_vol
        diversification = float(weights @ asset_vols / portfolio_vol)
    else:
        marginal = risk_share = None
        diversification = None
        warnings.append("Portfolio volatility is zero; risk contributions are undefined.")

    # Benchmark alignment (portfolio NAV vs benchmark on shared dates).
    relative: RelativeMetrics | None = None
    bench_dates: list[date] = []
    bench_cum: list[float] = []
    port_on_bench: list[float] = []
    asset_betas: dict[str, float | None] = {s: None for s in symbols}
    if benchmark is None:
        warnings.append(f"Benchmark '{benchmark_symbol}' has no history in this window; relative metrics omitted.")
    else:
        nav_by_date = dict(zip(dates, nav.tolist()))
        shared, both = align_on_common_dates({"p": nav_by_date, "b": benchmark.adjusted_closes()})
        if len(shared) >= 3:
            relative, rel_warnings = relative_metrics(
                shared, both["p"], both["b"], annual_risk_free_rate, infer_periods_per_year(shared)
            )
            warnings.extend(rel_warnings)
            bench_dates = shared
            bench_cum = cumulative_returns(both["b"])
            port_on_bench = cumulative_returns(both["p"])
            bench_series = np.array([benchmark.adjusted_closes().get(d, np.nan) for d in dates])
            mask = ~np.isnan(bench_series)
            if mask.sum() >= 3:
                idx = np.flatnonzero(mask)
                bench_ret = bench_series[idx][1:] / bench_series[idx][:-1] - 1.0
                bench_var = float(np.var(bench_ret, ddof=1))
                for column, symbol in enumerate(symbols):
                    asset_ret = prices[idx, column][1:] / prices[idx, column][:-1] - 1.0
                    if not is_effectively_zero(math.sqrt(bench_var)):
                        asset_betas[symbol] = float(np.cov(asset_ret, bench_ret, ddof=1)[0, 1] / bench_var)
        else:
            warnings.append("Portfolio and benchmark share fewer than three dates; relative metrics omitted.")

    if model is RebalancingModel.BUY_AND_HOLD:
        contribution_method = "exact: initial weight x asset total return (sums to portfolio total return)"
        contributions = weights * (prices[-1] / prices[0] - 1.0)
    else:
        contribution_method = (
            "arithmetic approximation: sum of daily weighted returns (does not compound to the "
            "portfolio total exactly)"
        )
        contributions = (asset_returns * weights).sum(axis=0)

    assets: list[AssetContribution] = []
    for column, holding in enumerate(holdings):
        series = prices[:, column]
        try:
            cagr = calendar_annualized_return(float(series[0]), float(series[-1]), dates[0], dates[-1])
        except (ValueError, OverflowError):
            cagr = None
            warnings.append(f"{holding.ticker}: annualized return is undefined for this window.")
        assets.append(
            AssetContribution(
                symbol=holding.ticker,
                weight=holding.weight,
                ending_weight=float(ending_weights[column]),
                total_return=float(series[-1] / series[0] - 1.0),
                annualized_return=cagr,
                annualized_volatility=float(asset_vols[column]) if len(series) > 2 else None,
                beta=asset_betas[holding.ticker],
                return_contribution=float(contributions[column]),
                risk_contribution=float(risk_share[column]) if risk_share is not None else None,
                marginal_risk=float(marginal[column]) if marginal is not None else None,
            )
        )

    correlation = _correlation_matrix(asset_returns)
    return PortfolioAnalysis(
        model=model,
        holdings=tuple(holdings),
        start=dates[0],
        end=dates[-1],
        periods_per_year=periods,
        performance=performance,
        relative=relative,
        assets=tuple(assets),
        correlation_symbols=tuple(symbols),
        correlation=correlation,
        diversification_ratio=diversification,
        contribution_method=contribution_method,
        series=PortfolioSeries(
            dates=tuple(dates),
            cumulative_return=tuple((nav - 1.0).tolist()),
            drawdown=tuple(drawdown_series(nav.tolist())),
            benchmark_dates=tuple(bench_dates),
            benchmark_cumulative_return=tuple(bench_cum),
            portfolio_cumulative_on_benchmark_dates=tuple(port_on_bench),
        ),
        warnings=tuple(dict.fromkeys(warnings)),
        assumptions=ASSUMPTIONS,
    )


def _correlation_matrix(returns: np.ndarray) -> tuple[tuple[float | None, ...], ...]:
    n = returns.shape[1]
    stds = returns.std(axis=0, ddof=1)
    if n == 1:
        return ((None,),) if is_effectively_zero(stds[0]) else ((1.0,),)
    with np.errstate(invalid="ignore", divide="ignore"):
        matrix = np.corrcoef(returns, rowvar=False)
    rows: list[tuple[float | None, ...]] = []
    for i in range(n):
        row: list[float | None] = []
        for j in range(n):
            value = matrix[i, j]
            if is_effectively_zero(stds[i]) or is_effectively_zero(stds[j]) or not math.isfinite(value):
                row.append(None)
            else:
                row.append(float(max(-1.0, min(1.0, value))))
        rows.append(tuple(row))
    return tuple(rows)


# ── Historical stress episodes ─────────────────────────────────────────


@dataclass(frozen=True)
class StressEpisode:
    key: str
    name: str
    start: date
    end: date
    description: str


STRESS_EPISODES = (
    StressEpisode("gfc", "Global Financial Crisis", date(2007, 10, 9), date(2009, 3, 9),
                  "S&P 500 peak-to-trough during the 2007-09 financial crisis."),
    StressEpisode("eu_debt_2011", "2011 US downgrade / euro debt crisis", date(2011, 7, 22), date(2011, 10, 3),
                  "Sell-off around the US sovereign downgrade and euro-area debt stress."),
    StressEpisode("q4_2018", "Q4 2018 sell-off", date(2018, 9, 20), date(2018, 12, 24),
                  "Rate-hike and growth-scare sell-off in late 2018."),
    StressEpisode("covid", "COVID-19 crash", date(2020, 2, 19), date(2020, 3, 23),
                  "Pandemic shock from the February 2020 peak to the March trough."),
    StressEpisode("rates_2022", "2022 rate shock", date(2022, 1, 3), date(2022, 10, 12),
                  "Inflation and rapid policy tightening; stocks and bonds fell together."),
)


@dataclass(frozen=True)
class StressResult:
    episode: StressEpisode
    computable: bool
    portfolio_return: float | None
    benchmark_return: float | None
    portfolio_max_drawdown: float | None
    missing_symbols: tuple[str, ...]


def stress_test(
    holdings: Sequence[PortfolioPosition],
    histories: Mapping[str, PriceHistory],
    benchmark: PriceHistory | None,
    episodes: Sequence[StressEpisode] = STRESS_EPISODES,
) -> list[StressResult]:
    """Replay each historical episode with the current weights, buy-and-hold
    from the episode start. Episodes where any holding lacks history are
    reported as not computable rather than silently re-weighted."""
    validate_holdings(holdings)
    results: list[StressResult] = []
    weights = np.array([h.weight for h in holdings], dtype=float)
    for episode in episodes:
        missing: list[str] = []
        windows: dict[str, dict[date, float]] = {}
        for holding in holdings:
            history = histories.get(holding.ticker)
            closes = (
                {d: v for d, v in history.adjusted_closes().items() if episode.start <= d <= episode.end}
                if history
                else {}
            )
            # The holding must cover (almost) the whole episode: a series that
            # starts late or stops early would silently shorten the replay.
            if not _covers_episode(closes, episode):
                missing.append(holding.ticker)
            windows[holding.ticker] = closes
        if missing:
            results.append(StressResult(episode, False, None, None, None, tuple(missing)))
            continue
        dates, aligned = align_on_common_dates(windows)
        if len(dates) < 2:
            results.append(StressResult(episode, False, None, None, None, ()))
            continue
        prices = np.array([aligned[h.ticker] for h in holdings], dtype=float).T
        nav, _ = portfolio_nav(prices, weights, RebalancingModel.BUY_AND_HOLD)
        bench_return = None
        if benchmark is not None:
            # Measure the benchmark over the same first/last dates as the
            # portfolio so the two returns are directly comparable.
            bench = benchmark.adjusted_closes()
            if dates[0] in bench and dates[-1] in bench:
                bench_return = bench[dates[-1]] / bench[dates[0]] - 1.0
        results.append(
            StressResult(
                episode=episode,
                computable=True,
                portfolio_return=float(nav[-1] - 1.0),
                benchmark_return=bench_return,
                portfolio_max_drawdown=float(min(drawdown_series(nav.tolist()))),
                missing_symbols=(),
            )
        )
    return results


def _covers_episode(closes: Mapping[date, float], episode: StressEpisode) -> bool:
    if not closes:
        return False
    return min(closes) <= episode.start + _EPISODE_GRACE and max(closes) >= episode.end - _EPISODE_GRACE
