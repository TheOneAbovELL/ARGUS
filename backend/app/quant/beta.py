"""Systematic market-risk calculations."""

import math
import statistics
from collections.abc import Sequence


def beta(asset_returns: Sequence[float], benchmark_returns: Sequence[float]) -> float:
    """Calculate asset covariance with the benchmark divided by benchmark variance."""
    if len(asset_returns) != len(benchmark_returns):
        raise ValueError("Asset and benchmark returns must be aligned.")
    if len(asset_returns) < 2:
        raise ValueError("At least two aligned returns are required for beta.")
    if any(
        not math.isfinite(value) for value in (*asset_returns, *benchmark_returns)
    ):
        raise ValueError("Returns must be finite numbers.")

    benchmark_variance = statistics.variance(benchmark_returns)
    if benchmark_variance == 0:
        raise ValueError("Beta is undefined when benchmark variance is zero.")
    return statistics.covariance(asset_returns, benchmark_returns) / benchmark_variance
