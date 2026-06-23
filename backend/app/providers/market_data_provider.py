"""Market data provider contracts and implementations."""

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
import math
from time import sleep
from typing import Any, Callable, Mapping, Protocol

import yfinance as yf


@dataclass(frozen=True)
class MarketDataSnapshot:
    """Normalized market data returned by any market data provider."""

    ticker: str
    company_name: str
    sector: str
    current_price: float


@dataclass(frozen=True)
class PricePoint:
    """One adjusted daily closing price."""

    date: date
    adjusted_close: float


@dataclass(frozen=True)
class PriceHistory:
    """Chronologically ordered adjusted prices for one ticker."""

    ticker: str
    points: tuple[PricePoint, ...]


class MarketDataProvider(Protocol):
    """Interface that all market data providers must implement."""

    async def get_company_snapshot(self, ticker: str) -> MarketDataSnapshot | None:
        """Return market data for a ticker, or None when unavailable."""

    async def get_price_history(
        self, ticker: str, period: str = "1y"
    ) -> PriceHistory | None:
        """Return adjusted daily prices, or None when unavailable."""


class MarketDataProviderUnavailableError(Exception):
    """Raised when an upstream market data provider cannot be reached."""


class YFinanceProvider:
    """Adapt yfinance responses to ARGUS's stable provider contract.

    yfinance and Yahoo Finance are external systems. Short retries absorb
    transient failures while the provider-specific exception prevents network
    and rate-limit details from leaking into the service layer.
    """

    def __init__(
        self,
        max_attempts: int = 2,
        retry_delay_seconds: float = 0.25,
        ticker_factory: Callable[[str], Any] = yf.Ticker,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")

        self._max_attempts = max_attempts
        self._retry_delay_seconds = retry_delay_seconds
        self._ticker_factory = ticker_factory
        self._sleeper = sleeper

    async def get_company_snapshot(self, ticker: str) -> MarketDataSnapshot | None:
        """Fetch a quote without blocking FastAPI's event loop."""
        return await asyncio.to_thread(self._get_company_snapshot_sync, ticker)

    def _get_company_snapshot_sync(self, ticker: str) -> MarketDataSnapshot | None:
        """Run blocking yfinance I/O and retries inside a worker thread."""
        last_error: Exception | None = None

        for attempt in range(self._max_attempts):
            try:
                info = self._ticker_factory(ticker).info
                return self._to_snapshot(ticker, info)
            except Exception as exc:  # yfinance exposes several transport errors
                last_error = exc
                if attempt + 1 < self._max_attempts:
                    self._sleeper(self._retry_delay_seconds)

        raise MarketDataProviderUnavailableError(
            "Yahoo Finance is temporarily unavailable."
        ) from last_error

    async def get_price_history(
        self, ticker: str, period: str = "1y"
    ) -> PriceHistory | None:
        """Fetch adjusted daily history without blocking the event loop."""
        return await asyncio.to_thread(self._get_price_history_sync, ticker, period)

    def _get_price_history_sync(
        self, ticker: str, period: str
    ) -> PriceHistory | None:
        """Run blocking yfinance history I/O and retries in a worker thread."""
        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                frame = self._ticker_factory(ticker).history(
                    period=period,
                    interval="1d",
                    auto_adjust=True,
                    actions=False,
                )
                if frame is None or frame.empty or "Close" not in frame:
                    return None
                points = tuple(
                    PricePoint(
                        date=index.date(),
                        adjusted_close=float(close),
                    )
                    for index, close in frame["Close"].items()
                    if isinstance(close, (int, float)) and math.isfinite(close) and close > 0
                )
                return PriceHistory(ticker=ticker, points=points) if points else None
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self._max_attempts:
                    self._sleeper(self._retry_delay_seconds)

        raise MarketDataProviderUnavailableError(
            "Yahoo Finance history is temporarily unavailable."
        ) from last_error

    @staticmethod
    def _to_snapshot(
        ticker: str, info: Mapping[str, Any] | None
    ) -> MarketDataSnapshot | None:
        """Translate provider-shaped data into ARGUS's domain snapshot."""
        if not info:
            return None

        price = next(
            (
                info.get(field)
                for field in ("currentPrice", "regularMarketPrice", "previousClose")
                if isinstance(info.get(field), (int, float))
            ),
            None,
        )
        if price is None:
            return None

        return MarketDataSnapshot(
            ticker=ticker,
            company_name=info.get("longName") or info.get("shortName") or ticker,
            sector=info.get("sector") or "Unknown",
            current_price=float(price),
        )


class MockMarketDataProvider:
    """Deterministic market data provider used before external integrations."""

    _mock_data: dict[str, MarketDataSnapshot] = {
        "NVDA": MarketDataSnapshot(
            ticker="NVDA",
            company_name="NVIDIA Corporation",
            sector="Technology",
            current_price=182.43,
        ),
    }

    async def get_company_snapshot(self, ticker: str) -> MarketDataSnapshot | None:
        """Return mock market data for supported tickers."""
        return self._mock_data.get(ticker)

    async def get_price_history(
        self, ticker: str, period: str = "1y"
    ) -> PriceHistory | None:
        """Return deterministic history for local development and tests."""
        price_paths = {
            "NVDA": (100.0, 104.0, 102.0, 108.0, 112.0),
            "SPY": (100.0, 102.0, 101.0, 104.0, 106.0),
        }
        prices = price_paths.get(ticker)
        if prices is None:
            return None
        start = date(2025, 1, 2)
        return PriceHistory(
            ticker=ticker,
            points=tuple(
                PricePoint(start + timedelta(days=index), price)
                for index, price in enumerate(prices)
            ),
        )
