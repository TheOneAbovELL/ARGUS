"""Market data service for Phase 2."""

from app.providers.market_data_provider import (
    MarketDataProvider,
    MarketDataProviderUnavailableError,
    MarketDataSnapshot,
)


class MarketDataNotFoundError(Exception):
    """Raised when the requested ticker is not available in the data source."""


class MarketDataUnavailableError(Exception):
    """Raised when market data is temporarily unavailable."""


class MarketDataService:
    """Retrieve market data for supported tickers.

    The service depends on a provider abstraction so the backing data source can
    change without changing API routes.
    """

    def __init__(self, provider: MarketDataProvider) -> None:
        """Create the service with a market data provider."""
        self._provider = provider

    def get_company_snapshot(self, ticker: str) -> MarketDataSnapshot:
        """Return a normalized market data snapshot for one ticker."""
        try:
            snapshot = self._provider.get_company_snapshot(ticker)
        except MarketDataProviderUnavailableError as exc:
            raise MarketDataUnavailableError(
                "Market data is temporarily unavailable. Please try again later."
            ) from exc

        if snapshot is None:
            raise MarketDataNotFoundError(
                f"Market data is not available for ticker '{ticker}'."
            )

        return snapshot
