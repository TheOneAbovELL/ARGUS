"""Tests for the portfolio application service."""

import asyncio

from app.portfolio.engine import PortfolioPosition, PortfolioResult
from app.quant.metrics import QuantMetrics
from app.schemas.portfolio import PortfolioHolding
from app.services.portfolio import PortfolioService


class RecordingPortfolioEngine:
    """Record normalized positions and return fixed analytics."""

    positions: list[PortfolioPosition]

    async def analyze(self, holdings: list[PortfolioPosition]) -> PortfolioResult:
        self.positions = holdings
        return PortfolioResult(
            tuple(holdings),
            QuantMetrics(0.12, 0.2, 0.6, 1.1, -0.15),
        )


def test_portfolio_service_normalizes_weights_and_builds_response() -> None:
    engine = RecordingPortfolioEngine()
    service = PortfolioService(engine)

    response = asyncio.run(
        service.analyze_portfolio(
            [
                PortfolioHolding(ticker="NVDA", weight=60),
                PortfolioHolding(ticker="MSFT", weight=40),
            ]
        )
    )

    assert engine.positions == [
        PortfolioPosition("NVDA", 0.6),
        PortfolioPosition("MSFT", 0.4),
    ]
    assert response.portfolio_return == 0.12
    assert response.portfolio_beta == 1.1
    assert [holding.ticker for holding in response.holdings] == ["NVDA", "MSFT"]
