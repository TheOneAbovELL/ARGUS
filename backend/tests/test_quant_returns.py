"""Tests for deterministic return calculations."""

import pytest

from app.quant.returns import annual_return, daily_returns


def test_daily_returns_calculates_price_changes() -> None:
    assert daily_returns([100.0, 110.0, 99.0]) == pytest.approx([0.1, -0.1])


def test_annual_return_uses_compound_growth() -> None:
    assert annual_return([100.0, 121.0], trading_days=2) == pytest.approx(0.4641)


def test_returns_reject_invalid_prices() -> None:
    with pytest.raises(ValueError):
        daily_returns([100.0, 0.0])
