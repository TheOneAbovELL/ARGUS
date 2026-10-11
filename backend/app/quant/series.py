"""Rolling-window statistics and series alignment."""

import math
from collections.abc import Mapping, Sequence
from datetime import date

import numpy as np

from app.quant.returns import TRADING_DAYS_PER_YEAR


def rolling_volatility(
    returns: Sequence[float],
    window: int = 63,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> list[float | None]:
    """Annualized sample standard deviation over a trailing window.

    The first ``window - 1`` positions are ``None`` (insufficient data) rather
    than zero."""
    if window < 2:
        raise ValueError("window must be at least 2.")
    values = np.asarray(returns, dtype=float)
    result: list[float | None] = [None] * len(values)
    if len(values) < window:
        return result
    windows = np.lib.stride_tricks.sliding_window_view(values, window)
    stds = windows.std(axis=1, ddof=1) * math.sqrt(periods_per_year)
    for offset, value in enumerate(stds):
        result[window - 1 + offset] = float(value)
    return result


def rolling_beta(
    asset: Sequence[float], benchmark: Sequence[float], window: int = 63
) -> list[float | None]:
    if len(asset) != len(benchmark):
        raise ValueError("Asset and benchmark returns must be aligned.")
    a = np.asarray(asset, dtype=float)
    b = np.asarray(benchmark, dtype=float)
    result: list[float | None] = [None] * len(a)
    if len(a) < window:
        return result
    aw = np.lib.stride_tricks.sliding_window_view(a, window)
    bw = np.lib.stride_tricks.sliding_window_view(b, window)
    a_dev = aw - aw.mean(axis=1, keepdims=True)
    b_dev = bw - bw.mean(axis=1, keepdims=True)
    cov = (a_dev * b_dev).sum(axis=1)
    var = (b_dev * b_dev).sum(axis=1)
    for offset, (c, v) in enumerate(zip(cov, var)):
        result[window - 1 + offset] = float(c / v) if v > 1e-24 * window else None
    return result


def align_on_common_dates(
    series: Mapping[str, Mapping[date, float]],
) -> tuple[list[date], dict[str, list[float]]]:
    """Intersect the date sets of several series (inner join).

    Inner-joining avoids forward-filling prices, which would fabricate
    zero-return days for assets that did not trade."""
    if not series:
        return [], {}
    common = sorted(set.intersection(*(set(values) for values in series.values())))
    return common, {name: [values[d] for d in common] for name, values in series.items()}
