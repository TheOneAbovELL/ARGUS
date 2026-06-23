"""Return calculations from ordered price observations."""

import math
from collections.abc import Sequence

TRADING_DAYS_PER_YEAR = 252


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
