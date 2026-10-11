"""Benchmark-relative statistics from aligned periodic returns."""

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from app.quant.beta import beta as _beta
from app.quant.returns import TRADING_DAYS_PER_YEAR, is_effectively_zero


def _aligned(asset: Sequence[float], benchmark: Sequence[float], minimum: int = 2) -> None:
    if len(asset) != len(benchmark):
        raise ValueError("Asset and benchmark returns must be aligned.")
    if len(asset) < minimum:
        raise ValueError(f"At least {minimum} aligned returns are required.")
    if any(not math.isfinite(v) for v in (*asset, *benchmark)):
        raise ValueError("Returns must be finite numbers.")


def correlation(a: Sequence[float], b: Sequence[float]) -> float:
    """Pearson correlation; undefined when either series has zero variance."""
    _aligned(a, b)
    if is_effectively_zero(statistics.pstdev(a)) or is_effectively_zero(statistics.pstdev(b)):
        raise ValueError("Correlation is undefined for a constant series.")
    value = statistics.correlation(a, b)
    return max(-1.0, min(1.0, value))


@dataclass(frozen=True)
class RegressionStats:
    """Single-index (CAPM-style) OLS of asset excess returns on benchmark
    excess returns. ``alpha`` is the annualized intercept (arithmetic)."""

    beta: float
    alpha: float
    correlation: float | None  # undefined when the asset's returns are constant
    r_squared: float | None


def regression_stats(
    asset: Sequence[float],
    benchmark: Sequence[float],
    annual_risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> RegressionStats:
    _aligned(asset, benchmark, minimum=3)
    rf = (1.0 + annual_risk_free_rate) ** (1.0 / periods_per_year) - 1.0
    asset_excess = [value - rf for value in asset]
    bench_excess = [value - rf for value in benchmark]
    slope = _beta(asset_excess, bench_excess)
    intercept = statistics.mean(asset_excess) - slope * statistics.mean(bench_excess)
    try:
        rho: float | None = correlation(asset_excess, bench_excess)
    except ValueError:
        rho = None  # constant asset: beta (0) and alpha are defined, correlation is not
    return RegressionStats(
        beta=slope,
        alpha=intercept * periods_per_year,
        correlation=rho,
        r_squared=rho * rho if rho is not None else None,
    )


def tracking_error(
    asset: Sequence[float],
    benchmark: Sequence[float],
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Annualized standard deviation of active (asset minus benchmark) returns."""
    _aligned(asset, benchmark)
    active = [a - b for a, b in zip(asset, benchmark)]
    return statistics.stdev(active) * math.sqrt(periods_per_year)


def information_ratio(
    asset: Sequence[float],
    benchmark: Sequence[float],
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Annualized mean active return divided by tracking error."""
    error = tracking_error(asset, benchmark, periods_per_year)
    if is_effectively_zero(error):
        raise ValueError("Information ratio is undefined when tracking error is zero.")
    active_mean = statistics.mean(a - b for a, b in zip(asset, benchmark))
    return active_mean * periods_per_year / error
