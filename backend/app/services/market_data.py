"""Market data service for Phase 2."""

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass

from app.providers.market_data_provider import (
    MarketDataProvider,
    MarketDataProviderUnavailableError,
    MarketDataSnapshot,
)
from app.quant.metrics import QuantDataError, QuantEngine, QuantMetrics


@dataclass(frozen=True)
class CompanyAnalysis:
    """Company snapshot combined with deterministic quantitative metrics."""

    snapshot: MarketDataSnapshot
    metrics: QuantMetrics


class MarketDataNotFoundError(Exception):
    """Raised when the requested ticker is not available in the data source."""


class MarketDataUnavailableError(Exception):
    """Raised when market data is temporarily unavailable."""


class MarketDataService:
    """Retrieve market data for supported tickers.

    The service depends on a provider abstraction so the backing data source can
    change without changing API routes.
    """

    def __init__(
        self,
        provider: MarketDataProvider,
        quant_engine: QuantEngine | None = None,
    ) -> None:
        """Create the service with a market data provider."""
        self._provider = provider
        self._quant_engine = quant_engine or QuantEngine(provider)

    async def get_company_snapshot(self, ticker: str) -> MarketDataSnapshot:
        """Return a normalized market data snapshot for one ticker."""
        try:
            snapshot = await self._provider.get_company_snapshot(ticker)
        except MarketDataProviderUnavailableError as exc:
            raise MarketDataUnavailableError(
                "Market data is temporarily unavailable. Please try again later."
            ) from exc

        if snapshot is None:
            raise MarketDataNotFoundError(
                f"Market data is not available for ticker '{ticker}'."
            )

        return snapshot

    async def analyze_company(self, ticker: str) -> CompanyAnalysis:
        """Combine company data with quantitative analytics concurrently."""
        try:
            snapshot, metrics = await asyncio.gather(
                self.get_company_snapshot(ticker),
                self._quant_engine.analyze(ticker),
            )
        except QuantDataError as exc:
            raise MarketDataNotFoundError(
                f"Analytics are not available for ticker '{ticker}': {exc}"
            ) from exc
        except MarketDataProviderUnavailableError as exc:
            raise MarketDataUnavailableError(
                "Market data is temporarily unavailable. Please try again later."
            ) from exc
        return CompanyAnalysis(snapshot=snapshot, metrics=metrics)

    async def get_company_snapshots(
        self, tickers: Iterable[str]
    ) -> list[MarketDataSnapshot]:
        """Retrieve independent ticker snapshots concurrently.

        asyncio.gather schedules all provider coroutines together while
        preserving the input order in the returned list.
        """
        return await asyncio.gather(
            *(self.get_company_snapshot(ticker) for ticker in tickers)
        )
