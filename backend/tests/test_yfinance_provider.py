"""Unit tests for the Yahoo Finance provider adapter."""

import asyncio

import pytest

from app.providers.market_data_provider import (
    MarketDataProviderUnavailableError,
    YFinanceProvider,
)


class FakeTicker:
    """Small stand-in for yfinance.Ticker."""

    def __init__(self, info: dict[str, object]) -> None:
        self.info = info


def test_yfinance_provider_adapts_external_response() -> None:
    """Yahoo-shaped dictionaries should become stable domain snapshots."""
    provider = YFinanceProvider(
        ticker_factory=lambda ticker: FakeTicker(
            {
                "longName": "NVIDIA Corporation",
                "sector": "Technology",
                "currentPrice": 200.5,
            }
        )
    )

    snapshot = asyncio.run(provider.get_company_snapshot("NVDA"))

    assert snapshot is not None
    assert snapshot.ticker == "NVDA"
    assert snapshot.company_name == "NVIDIA Corporation"
    assert snapshot.sector == "Technology"
    assert snapshot.current_price == 200.5


def test_yfinance_provider_uses_safe_field_fallbacks() -> None:
    """Alternative Yahoo fields should cover partial quote responses."""
    provider = YFinanceProvider(
        ticker_factory=lambda ticker: FakeTicker(
            {"shortName": "Example Inc.", "regularMarketPrice": 12}
        )
    )

    snapshot = asyncio.run(provider.get_company_snapshot("TEST"))

    assert snapshot is not None
    assert snapshot.company_name == "Example Inc."
    assert snapshot.sector == "Unknown"
    assert snapshot.current_price == 12.0


def test_yfinance_provider_returns_none_when_quote_has_no_price() -> None:
    """A response without a usable price represents a missing ticker."""
    provider = YFinanceProvider(
        ticker_factory=lambda ticker: FakeTicker({"longName": "No Quote"})
    )

    assert asyncio.run(provider.get_company_snapshot("MISSING")) is None


def test_yfinance_provider_retries_then_wraps_network_failure() -> None:
    """Transient failures should be retried and hidden behind our contract."""
    attempts: list[str] = []
    delays: list[float] = []

    def failing_factory(ticker: str) -> FakeTicker:
        attempts.append(ticker)
        raise ConnectionError("network is down")

    provider = YFinanceProvider(
        max_attempts=3,
        retry_delay_seconds=0.1,
        ticker_factory=failing_factory,
        sleeper=delays.append,
    )

    with pytest.raises(MarketDataProviderUnavailableError):
        asyncio.run(provider.get_company_snapshot("NVDA"))

    assert attempts == ["NVDA", "NVDA", "NVDA"]
    assert delays == [0.1, 0.1]


def test_yfinance_provider_normalizes_current_news_shape() -> None:
    """Nested yfinance news records should become stable news items."""

    class NewsTicker:
        news = [
            {
                "content": {
                    "title": "NVIDIA announces a new platform",
                    "provider": {"displayName": "Example Wire"},
                    "canonicalUrl": {"url": "https://example.com/story"},
                    "pubDate": "2026-01-01T00:00:00Z",
                }
            }
        ]

    provider = YFinanceProvider(ticker_factory=lambda ticker: NewsTicker())
    items = asyncio.run(provider.get_company_news("NVDA"))

    assert len(items) == 1
    assert items[0].headline == "NVIDIA announces a new platform"
    assert items[0].publisher == "Example Wire"
    assert items[0].url == "https://example.com/story"
