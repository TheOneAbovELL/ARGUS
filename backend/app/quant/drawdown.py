"""Peak-to-trough loss calculations."""

from collections.abc import Sequence

from app.quant.returns import _validate_prices


def maximum_drawdown(prices: Sequence[float]) -> float:
    """Return the worst percentage decline from a prior price peak."""
    _validate_prices(prices)
    peak = prices[0]
    worst_drawdown = 0.0
    for price in prices:
        peak = max(peak, price)
        worst_drawdown = min(worst_drawdown, price / peak - 1.0)
    return worst_drawdown
