"""Tests for the Sharpe ratio."""

import math
import statistics

import pytest

from app.quant.sharpe import sharpe_ratio


def test_sharpe_ratio_annualizes_risk_adjusted_return() -> None:
    values = [0.01, -0.005, 0.02]
    expected = statistics.mean(values) / statistics.stdev(values) * math.sqrt(252)
    assert sharpe_ratio(values) == pytest.approx(expected)


def test_sharpe_ratio_rejects_zero_volatility() -> None:
    with pytest.raises(ValueError):
        sharpe_ratio([0.01, 0.01, 0.01])
