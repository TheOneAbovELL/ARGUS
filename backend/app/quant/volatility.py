"""Annualized volatility calculations."""

import math
import statistics
from collections.abc import Sequence

from app.quant.returns import TRADING_DAYS_PER_YEAR


def annualized_volatility(
    returns: Sequence[float], trading_days: int = TRADING_DAYS_PER_YEAR
) -> float:
    """Annualize the sample standard deviation of periodic returns."""
    if len(returns) < 2:
        raise ValueError("At least two returns are required for volatility.")
    if any(not math.isfinite(value) for value in returns):
        raise ValueError("Returns must be finite numbers.")
    return statistics.stdev(returns) * math.sqrt(trading_days)
