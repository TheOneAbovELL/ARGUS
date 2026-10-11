"""Opt-in live checks against Yahoo Finance (free; network required).

Run with:  ARGUS_RUN_LIVE_TESTS=1 pytest -m integration
"""

import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest

from app.providers.models import DataMode
from app.providers.yahoo import YahooFinanceProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("ARGUS_RUN_LIVE_TESTS") != "1", reason="set ARGUS_RUN_LIVE_TESTS=1"),
]


def test_live_quote_history_and_unknown_symbol() -> None:
    provider = YahooFinanceProvider(max_attempts=2)
    quote = asyncio.run(provider.get_quote("MSFT"))
    assert quote is not None and quote.price > 0 and quote.provenance.mode is DataMode.DELAYED
    today = datetime.now(UTC).date()
    history = asyncio.run(provider.get_history("MSFT", today - timedelta(days=60), today))
    assert history is not None and len(history.bars) > 30
    assert all(bar.adj_close > 0 for bar in history.bars)
    assert asyncio.run(provider.get_quote("ZZZZZZZZ1")) is None
