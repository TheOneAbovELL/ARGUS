"""Tests for market beta."""

import pytest

from app.quant.beta import beta


def test_beta_measures_covariance_relative_to_market_variance() -> None:
    benchmark = [0.01, -0.02, 0.03]
    asset = [value * 1.5 for value in benchmark]
    assert beta(asset, benchmark) == pytest.approx(1.5)


def test_beta_requires_aligned_returns() -> None:
    with pytest.raises(ValueError):
        beta([0.01, 0.02], [0.01])
