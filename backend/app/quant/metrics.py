"""Aggregate metric sets computed from validated, date-indexed series.

Each metric is computed independently. When a metric is mathematically
undefined for the input (e.g. Sharpe with zero volatility) it is reported as
``None`` together with a human-readable warning — never as a misleading zero —
and the remaining metrics are still returned.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

from app.quant.drawdown import drawdown_stats
from app.quant.relative import information_ratio, regression_stats, tracking_error
from app.quant.returns import (
    _validate_prices,
    calendar_annualized_return,
    daily_returns,
    total_return,
)
from app.quant.risk import historical_cvar, historical_var, sortino_ratio
from app.quant.sharpe import sharpe_ratio
from app.quant.volatility import annualized_volatility

SHORT_HISTORY_THRESHOLD = 60
VAR_CONFIDENCE = 0.95


class QuantDataError(ValueError):
    """Raised when inputs cannot support any analysis at all."""


@dataclass(frozen=True)
class PerformanceMetrics:
    observations: int
    total_return: float
    annualized_return: float | None
    annualized_volatility: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown: float
    max_drawdown_peak: date
    max_drawdown_trough: date
    max_drawdown_recovery: date | None
    longest_drawdown_days: int
    current_drawdown: float
    var_95: float | None
    cvar_95: float | None
    best_period: float
    worst_period: float
    positive_periods_ratio: float


@dataclass(frozen=True)
class RelativeMetrics:
    observations: int
    beta: float | None
    alpha: float | None
    correlation: float | None
    r_squared: float | None
    tracking_error: float | None
    information_ratio: float | None
    benchmark_total_return: float
    benchmark_annualized_return: float | None
    excess_annualized_return: float | None


def _safe[T](name: str, fn: Callable[[], T], warnings: list[str]) -> T | None:
    try:
        return fn()
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        warnings.append(f"{name}: {exc}")
        return None


def performance_metrics(
    dates: Sequence[date],
    values: Sequence[float],
    annual_risk_free_rate: float,
    periods_per_year: int,
) -> tuple[PerformanceMetrics, list[str]]:
    """Return/risk metrics for one value series (prices or portfolio NAV)."""
    if len(dates) != len(values):
        raise QuantDataError("Dates and values must be aligned.")
    if len(values) < 3:
        raise QuantDataError("At least three price observations are required.")
    try:
        _validate_prices(values)
    except ValueError as exc:
        raise QuantDataError(str(exc)) from exc

    warnings: list[str] = []
    returns = daily_returns(values)
    if len(returns) < SHORT_HISTORY_THRESHOLD:
        warnings.append(
            f"Only {len(returns)} periodic returns are available; annualized statistics "
            "from short samples are unreliable."
        )
    dd = drawdown_stats(values)
    return (
        PerformanceMetrics(
            observations=len(returns),
            total_return=total_return(values),
            annualized_return=_safe(
                "annualized_return",
                lambda: calendar_annualized_return(values[0], values[-1], dates[0], dates[-1]),
                warnings,
            ),
            annualized_volatility=_safe(
                "annualized_volatility",
                lambda: annualized_volatility(returns, periods_per_year),
                warnings,
            ),
            sharpe_ratio=_safe(
                "sharpe_ratio",
                lambda: sharpe_ratio(returns, annual_risk_free_rate, periods_per_year),
                warnings,
            ),
            sortino_ratio=_safe(
                "sortino_ratio",
                lambda: sortino_ratio(returns, annual_risk_free_rate, periods_per_year),
                warnings,
            ),
            max_drawdown=dd.max_drawdown,
            max_drawdown_peak=dates[dd.peak_index],
            max_drawdown_trough=dates[dd.trough_index],
            max_drawdown_recovery=(
                dates[dd.recovery_index] if dd.recovery_index is not None else None
            ),
            longest_drawdown_days=dd.longest_underwater_periods,
            current_drawdown=dd.current_drawdown,
            var_95=_safe("var_95", lambda: historical_var(returns, VAR_CONFIDENCE), warnings),
            cvar_95=_safe("cvar_95", lambda: historical_cvar(returns, VAR_CONFIDENCE), warnings),
            best_period=max(returns),
            worst_period=min(returns),
            positive_periods_ratio=sum(1 for r in returns if r > 0) / len(returns),
        ),
        warnings,
    )


def relative_metrics(
    dates: Sequence[date],
    asset_values: Sequence[float],
    benchmark_values: Sequence[float],
    annual_risk_free_rate: float,
    periods_per_year: int,
) -> tuple[RelativeMetrics, list[str]]:
    """Benchmark-relative statistics on series already aligned to shared dates."""
    if not (len(dates) == len(asset_values) == len(benchmark_values)):
        raise QuantDataError("Asset and benchmark series must be aligned.")
    if len(dates) < 3:
        raise QuantDataError("At least three aligned observations are required.")
    warnings: list[str] = []
    asset_returns = daily_returns(asset_values)
    bench_returns = daily_returns(benchmark_values)
    regression = _safe(
        "beta/alpha",
        lambda: regression_stats(asset_returns, bench_returns, annual_risk_free_rate, periods_per_year),
        warnings,
    )
    asset_cagr = _safe(
        "annualized_return",
        lambda: calendar_annualized_return(asset_values[0], asset_values[-1], dates[0], dates[-1]),
        [],
    )
    bench_cagr = _safe(
        "benchmark_annualized_return",
        lambda: calendar_annualized_return(
            benchmark_values[0], benchmark_values[-1], dates[0], dates[-1]
        ),
        warnings,
    )
    return (
        RelativeMetrics(
            observations=len(asset_returns),
            beta=regression.beta if regression else None,
            alpha=regression.alpha if regression else None,
            correlation=regression.correlation if regression else None,
            r_squared=regression.r_squared if regression else None,
            tracking_error=_safe(
                "tracking_error",
                lambda: tracking_error(asset_returns, bench_returns, periods_per_year),
                warnings,
            ),
            information_ratio=_safe(
                "information_ratio",
                lambda: information_ratio(asset_returns, bench_returns, periods_per_year),
                warnings,
            ),
            benchmark_total_return=total_return(benchmark_values),
            benchmark_annualized_return=bench_cagr,
            excess_annualized_return=(
                asset_cagr - bench_cagr
                if asset_cagr is not None and bench_cagr is not None
                else None
            ),
        ),
        warnings,
    )
