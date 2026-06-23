"""Dependency wiring for portfolio analytics."""

from app.core.config import settings
from app.dependencies.market_data import get_market_data_provider
from app.portfolio.engine import PortfolioEngine
from app.services.portfolio import PortfolioService


def get_portfolio_service() -> PortfolioService:
    """Provide a configured portfolio analytics service."""
    engine = PortfolioEngine(
        provider=get_market_data_provider(),
        benchmark_ticker=settings.quant_benchmark_ticker,
        history_period=settings.quant_history_period,
        annual_risk_free_rate=settings.quant_annual_risk_free_rate,
    )
    return PortfolioService(engine)
