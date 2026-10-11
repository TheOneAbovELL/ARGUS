"""Return calculations from ordered price observations."""

import math
from collections.abc import Sequence
from datetime import date

TRADING_DAYS_PER_YEAR = 252

# Dispersion below this is treated as exactly zero. Floating-point arithmetic
# on a constant return series yields a stdev around 1e-17, which would turn
# an undefined ratio into an absurd one (e.g. a Sharpe ratio of 1e15).
DISPERSION_EPSILON = 1e-12


def is_effectively_zero(dispersion: float) -> bool:
    return abs(dispersion) < DISPERSION_EPSILON


def daily_returns(prices: Sequence[float]) -> list[float]:
    """Calculate simple close-to-close returns."""
    _validate_prices(prices)
    return [current / previous - 1.0 for previous, current in zip(prices, prices[1:])]


def annual_return(
    prices: Sequence[float], trading_days: int = TRADING_DAYS_PER_YEAR
) -> float:
    """Calculate annualized compound return (CAGR) from daily prices."""
    _validate_prices(prices)
    periods = len(prices) - 1
    return (prices[-1] / prices[0]) ** (trading_days / periods) - 1.0


def _validate_prices(prices: Sequence[float]) -> None:
    if len(prices) < 2:
        raise ValueError("At least two price observations are required.")
    if any(not math.isfinite(price) or price <= 0 for price in prices):
        raise ValueError("Prices must be positive finite numbers.")


def log_returns(prices: Sequence[float]) -> list[float]:
    """Calculate continuously compounded returns ``ln(p_t / p_{t-1})``."""
    _validate_prices(prices)
    return [math.log(current / previous) for previous, current in zip(prices, prices[1:])]


def cumulative_returns(prices: Sequence[float]) -> list[float]:
    """Growth relative to the first observation: ``p_t / p_0 - 1``."""
    _validate_prices(prices)
    first = prices[0]
    return [price / first - 1.0 for price in prices]


def total_return(prices: Sequence[float]) -> float:
    _validate_prices(prices)
    return prices[-1] / prices[0] - 1.0


def calendar_annualized_return(
    start_value: float, end_value: float, start: date, end: date
) -> float:
    """CAGR using elapsed calendar time (365.25-day years).

    Calendar time is robust to missing observations and to assets that trade
    on weekends, unlike ``periods / 252``."""
    _validate_prices([start_value, end_value])
    days = (end - start).days
    if days < 1:
        raise ValueError("Annualized return needs at least one elapsed day.")
    return (end_value / start_value) ** (365.25 / days) - 1.0


def infer_periods_per_year(dates: Sequence[date]) -> int:
    """Annualization factor from observation density: 365 for series that
    trade every calendar day (e.g. crypto), otherwise 252.

    Density (observations per 365.25 calendar days) is used instead of
    counting Saturdays/Sundays, so exchanges with a Friday/Saturday or
    Friday-only weekend (e.g. Tadawul, sessions Sun-Thu) still get 252."""
    if len(dates) < 2:
        return TRADING_DAYS_PER_YEAR
    span = (max(dates) - min(dates)).days
    if span <= 0:
        return TRADING_DAYS_PER_YEAR
    density = (len(dates) - 1) * 365.25 / span
    return 365 if density > (TRADING_DAYS_PER_YEAR + 365) / 2 else TRADING_DAYS_PER_YEAR
