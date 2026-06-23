"""Tests for portfolio construction and analytics."""

import asyncio
from datetime import date

import pytest

from app.portfolio.engine import (
    PortfolioEngine,
    PortfolioPosition,
    PortfolioValidationError,
)
from app.providers.market_data_provider import PriceHistory, PricePoint
from app.quant.metrics import QuantEngine


PRICE_PATHS = {
    "NVDA": [100.0, 104.0, 102.0, 108.0, 112.0],
    "MSFT": [100.0, 101.0, 103.0, 102.0, 105.0],
    "AAPL": [100.0, 99.0, 101.0, 104.0, 103.0],
    "SPY": [100.0, 102.0, 101.0, 104.0, 106.0],
}


class DeterministicPortfolioProvider:
    """Return fixed histories while recording overlapping requests."""

    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0

    async def get_price_history(
        self, ticker: str, period: str = "1y"
    ) -> PriceHistory | None:
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        prices = PRICE_PATHS.get(ticker)
        if prices is None:
            return None
        return PriceHistory(
            ticker,
            tuple(
                PricePoint(date(2025, 1, index + 1), price)
                for index, price in enumerate(prices)
            ),
        )


def test_portfolio_engine_reuses_quant_metrics_for_weighted_returns() -> None:
    provider = DeterministicPortfolioProvider()
    holdings = [
        PortfolioPosition("NVDA", 0.4),
        PortfolioPosition("MSFT", 0.3),
        PortfolioPosition("AAPL", 0.3),
    ]

    result = asyncio.run(PortfolioEngine(provider).analyze(holdings))

    portfolio_values = [1.0]
    for index in range(1, 5):
        weighted_return = sum(
            holding.weight
            * (PRICE_PATHS[holding.ticker][index] / PRICE_PATHS[holding.ticker][index - 1] - 1)
            for holding in holdings
        )
        portfolio_values.append(portfolio_values[-1] * (1 + weighted_return))
    expected = QuantEngine.compute_metrics(portfolio_values, PRICE_PATHS["SPY"])

    assert result.metrics == expected
    assert result.holdings == tuple(holdings)
    assert provider.maximum_active == 4


@pytest.mark.parametrize(
    "holdings",
    [
        [],
        [PortfolioPosition("NVDA", 0.8)],
        [PortfolioPosition("NVDA", 0.5), PortfolioPosition("NVDA", 0.5)],
        [PortfolioPosition("NVDA", 1.1), PortfolioPosition("MSFT", -0.1)],
    ],
)
def test_portfolio_engine_rejects_invalid_allocations(
    holdings: list[PortfolioPosition],
) -> None:
    with pytest.raises(PortfolioValidationError):
        asyncio.run(PortfolioEngine(DeterministicPortfolioProvider()).analyze(holdings))
