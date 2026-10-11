"""Downside-risk measures: Sortino ratio, historical VaR and CVaR."""

import math
import statistics
from collections.abc import Sequence

import numpy as np

from app.quant.returns import TRADING_DAYS_PER_YEAR, is_effectively_zero

MIN_TAIL_OBSERVATIONS = 20


def _check(returns: Sequence[float], minimum: int, label: str) -> None:
    if len(returns) < minimum:
        raise ValueError(f"At least {minimum} returns are required for {label}.")
    if any(not math.isfinite(value) for value in returns):
        raise ValueError("Returns must be finite numbers.")


def _daily_rate(annual_rate: float, periods: int) -> float:
    if annual_rate <= -1 or not math.isfinite(annual_rate):
        raise ValueError("The annual risk-free rate must be finite and greater than -1.")
    return (1.0 + annual_rate) ** (1.0 / periods) - 1.0


def downside_deviation(returns: Sequence[float], target: float = 0.0) -> float:
    """Root-mean-square of shortfalls below ``target`` across *all* periods
    (periods above target contribute zero)."""
    _check(returns, 2, "downside deviation")
    return math.sqrt(sum(min(value - target, 0.0) ** 2 for value in returns) / len(returns))


def sortino_ratio(
    returns: Sequence[float],
    annual_risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Annualized mean excess return over annualized downside deviation, with
    the per-period risk-free rate as the minimum acceptable return."""
    _check(returns, 2, "Sortino ratio")
    target = _daily_rate(annual_risk_free_rate, periods_per_year)
    deviation = downside_deviation(returns, target)
    if is_effectively_zero(deviation):
        raise ValueError("Sortino ratio is undefined when there are no returns below the target.")
    excess = statistics.mean(returns) - target
    return excess / deviation * math.sqrt(periods_per_year)


def historical_var(returns: Sequence[float], confidence: float = 0.95) -> float:
    """One-period historical Value at Risk, expressed as a return.

    It is the ``1 - confidence`` empirical quantile (linear interpolation), so
    ``-0.023`` at 95% means: on 5% of historical periods the return was -2.3%
    or worse. No distributional assumption is made."""
    if not 0.5 < confidence < 1:
        raise ValueError("confidence must be between 0.5 and 1.")
    _check(returns, MIN_TAIL_OBSERVATIONS, "historical VaR")
    return float(np.quantile(np.asarray(returns, dtype=float), 1.0 - confidence))


def historical_cvar(returns: Sequence[float], confidence: float = 0.95) -> float:
    """Expected shortfall: the mean return in periods at or below the VaR."""
    var = historical_var(returns, confidence)
    tail = [value for value in returns if value <= var]
    return statistics.mean(tail)
