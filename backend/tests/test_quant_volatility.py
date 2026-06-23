"""Tests for annualized volatility."""

import math
import statistics

import pytest

from app.quant.volatility import annualized_volatility


def test_volatility_annualizes_sample_standard_deviation() -> None:
    values = [0.01, -0.02, 0.03]
    expected = statistics.stdev(values) * math.sqrt(252)
    assert annualized_volatility(values) == pytest.approx(expected)
