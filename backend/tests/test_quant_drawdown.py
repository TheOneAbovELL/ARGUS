"""Tests for maximum drawdown."""

import pytest

from app.quant.drawdown import maximum_drawdown


def test_maximum_drawdown_finds_worst_peak_to_trough_loss() -> None:
    assert maximum_drawdown([100.0, 120.0, 90.0, 110.0]) == pytest.approx(-0.25)


def test_maximum_drawdown_is_zero_for_rising_prices() -> None:
    assert maximum_drawdown([100.0, 110.0, 120.0]) == 0.0
