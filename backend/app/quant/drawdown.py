"""Peak-to-trough loss calculations."""

from collections.abc import Sequence
from dataclasses import dataclass

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


def drawdown_series(prices: Sequence[float]) -> list[float]:
    """Running-peak drawdown ``p_t / max(p_0..p_t) - 1`` (always <= 0)."""
    _validate_prices(prices)
    peak = prices[0]
    series: list[float] = []
    for price in prices:
        peak = max(peak, price)
        series.append(price / peak - 1.0)
    return series


@dataclass(frozen=True)
class DrawdownStats:
    """Indices refer to positions in the input price sequence.

    ``longest_underwater_periods`` counts observations from a peak until the
    price first regains it (or until the end of the series if it never does).
    """

    max_drawdown: float
    peak_index: int
    trough_index: int
    recovery_index: int | None
    longest_underwater_periods: int
    current_drawdown: float


def drawdown_stats(prices: Sequence[float]) -> DrawdownStats:
    series = drawdown_series(prices)
    trough_index = min(range(len(series)), key=series.__getitem__)
    max_dd = series[trough_index]
    # The drawdown starts at the *latest* running peak before the trough (ties
    # with an earlier high must not move the reported peak date backwards).
    peak_index = max(range(trough_index + 1), key=lambda i: (prices[i], i))
    recovery_index = next(
        (i for i in range(trough_index + 1, len(prices)) if prices[i] >= prices[peak_index]),
        None,
    ) if max_dd < 0 else None

    longest = 0
    spell_start: int | None = None
    for index, value in enumerate(series):
        if value < 0 and spell_start is None:
            spell_start = index - 1
        elif value >= 0 and spell_start is not None:
            longest = max(longest, index - spell_start)
            spell_start = None
    if spell_start is not None:
        longest = max(longest, len(series) - 1 - spell_start)

    return DrawdownStats(
        max_drawdown=max_dd,
        peak_index=peak_index,
        trough_index=trough_index,
        recovery_index=recovery_index,
        longest_underwater_periods=longest,
        current_drawdown=series[-1],
    )
