"""Risk-adjusted return calculations."""

import math
import statistics
from collections.abc import Sequence

from app.quant.returns import TRADING_DAYS_PER_YEAR


def sharpe_ratio(
    returns: Sequence[float],
    annual_risk_free_rate: float = 0.0,
    trading_days: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Calculate the annualized Sharpe ratio from periodic returns."""
    if len(returns) < 2:
        raise ValueError("At least two returns are required for Sharpe ratio.")
    if annual_risk_free_rate <= -1 or not math.isfinite(annual_risk_free_rate):
        raise ValueError("The annual risk-free rate must be finite and greater than -1.")
    if any(not math.isfinite(value) for value in returns):
        raise ValueError("Returns must be finite numbers.")

    daily_risk_free_rate = (1.0 + annual_risk_free_rate) ** (1.0 / trading_days) - 1.0
    excess_returns = [value - daily_risk_free_rate for value in returns]
    daily_volatility = statistics.stdev(excess_returns)
    if daily_volatility == 0:
        raise ValueError("Sharpe ratio is undefined when return volatility is zero.")
    return statistics.mean(excess_returns) / daily_volatility * math.sqrt(trading_days)
