"""Opt-in live integration tests for Yahoo Finance."""

import os

import pytest

from app.providers.market_data_provider import YFinanceProvider


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("ARGUS_RUN_LIVE_TESTS") != "1",
        reason="set ARGUS_RUN_LIVE_TESTS=1 to call Yahoo Finance",
    ),
]


def test_yfinance_provider_returns_live_nvidia_snapshot() -> None:
    """The adapter should remain compatible with the live yfinance response."""
    snapshot = YFinanceProvider(max_attempts=2).get_company_snapshot("NVDA")

    assert snapshot is not None
    assert snapshot.ticker == "NVDA"
    assert snapshot.company_name
    assert snapshot.sector
    assert snapshot.current_price > 0
