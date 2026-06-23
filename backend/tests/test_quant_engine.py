"""Tests for quant engine orchestration."""

import asyncio
from datetime import date

import pytest

from app.providers.market_data_provider import PriceHistory, PricePoint
from app.quant.metrics import QuantEngine


def history(ticker: str, prices: list[float]) -> PriceHistory:
    return PriceHistory(
        ticker,
        tuple(
            PricePoint(date(2025, 1, day + 1), price)
            for day, price in enumerate(prices)
        ),
    )


class HistoryProvider:
    """Deterministic provider that records concurrent history calls."""

    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0

    async def get_price_history(
        self, ticker: str, period: str = "1y"
    ) -> PriceHistory:
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        if ticker == "SPY":
            return history(ticker, [100.0, 101.0, 99.0, 103.0])
        return history(ticker, [100.0, 102.0, 98.0, 106.0])


def test_quant_engine_aggregates_metrics_and_fetches_concurrently() -> None:
    provider = HistoryProvider()
    metrics = asyncio.run(QuantEngine(provider).analyze("NVDA"))

    assert metrics.annual_return > 0
    assert metrics.volatility > 0
    assert metrics.beta > 0
    assert metrics.max_drawdown == pytest.approx(98.0 / 102.0 - 1.0)
    assert provider.maximum_active == 2
