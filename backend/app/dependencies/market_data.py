"""Dependency wiring for market data components."""

from app.providers.market_data_provider import (
    MarketDataProvider,
    MockMarketDataProvider,
    YFinanceProvider,
)
from app.core.config import settings
from app.quant.metrics import QuantEngine
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
    provider = get_market_data_provider()
    quant_engine = QuantEngine(
        provider=provider,
        benchmark_ticker=settings.quant_benchmark_ticker,
        history_period=settings.quant_history_period,
        annual_risk_free_rate=settings.quant_annual_risk_free_rate,
    )
    return MarketDataService(provider=provider, quant_engine=quant_engine)
