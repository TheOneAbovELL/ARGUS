"""Market data provider contracts and implementations."""

from dataclasses import dataclass
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


class MarketDataProvider(Protocol):
    """Interface that all market data providers must implement."""

    def get_company_snapshot(self, ticker: str) -> MarketDataSnapshot | None:
        """Return market data for a ticker, or None when unavailable."""


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

    def get_company_snapshot(self, ticker: str) -> MarketDataSnapshot | None:
        """Fetch and normalize a quote, retrying transient upstream failures."""
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

    def get_company_snapshot(self, ticker: str) -> MarketDataSnapshot | None:
        """Return mock market data for supported tickers."""
        return self._mock_data.get(ticker)
