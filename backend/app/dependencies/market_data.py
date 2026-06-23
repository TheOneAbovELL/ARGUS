"""Dependency wiring for market data components."""

from app.providers.market_data_provider import (
    MarketDataProvider,
    MockMarketDataProvider,
    YFinanceProvider,
)
from app.core.config import settings
from app.services.market_data import MarketDataService


def get_market_data_provider() -> MarketDataProvider:
    """Provide the configured market data provider."""
    if settings.market_data_provider == "mock":
        return MockMarketDataProvider()

    return YFinanceProvider(
        max_attempts=settings.yfinance_max_attempts,
        retry_delay_seconds=settings.yfinance_retry_delay_seconds,
    )


def get_market_data_service() -> MarketDataService:
    """Provide a market data service with all dependencies wired."""
    return MarketDataService(provider=get_market_data_provider())
