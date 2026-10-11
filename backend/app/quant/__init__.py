"""Deterministic quantitative analytics for ARGUS.

Pure functions only: nothing in this package performs I/O or calls a model.
"""

from app.quant.metrics import (
    PerformanceMetrics,
    QuantDataError,
    RelativeMetrics,
    performance_metrics,
    relative_metrics,
)

__all__ = [
    "PerformanceMetrics",
    "QuantDataError",
    "RelativeMetrics",
    "performance_metrics",
    "relative_metrics",
]
