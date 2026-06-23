"""Tests for the ARGUS market data service layer."""

from app.services.market_data import MarketDataNotFoundError, MarketDataService
from app.providers.market_data_provider import MarketDataSnapshot


class EmptyMarketDataProvider:
    """Provider test double that never returns market data."""

    def get_company_snapshot(self, ticker: str) -> None:
        """Return no data for any ticker."""
        return None


class StaticMarketDataProvider:
    """Provider test double that returns one deterministic snapshot."""

    def get_company_snapshot(self, ticker: str) -> MarketDataSnapshot:
        """Return a fixed snapshot for service-layer tests."""
        return MarketDataSnapshot(
            ticker=ticker,
            company_name="Test Company",
            sector="Test Sector",
            current_price=1.23,
        )


def test_market_data_service_uses_injected_provider() -> None:
    """The service should delegate data retrieval to its configured provider."""
    service = MarketDataService(provider=StaticMarketDataProvider())

    snapshot = service.get_company_snapshot("TEST")

    assert snapshot.ticker == "TEST"
    assert snapshot.company_name == "Test Company"
    assert snapshot.sector == "Test Sector"
    assert snapshot.current_price == 1.23


def test_market_data_service_raises_error_when_provider_has_no_data() -> None:
    """Provider misses should become domain-specific service errors."""
    service = MarketDataService(provider=EmptyMarketDataProvider())

    try:
        service.get_company_snapshot("MSFT")
    except MarketDataNotFoundError as exc:
        assert "MSFT" in str(exc)
    else:
        raise AssertionError("Expected MarketDataNotFoundError")
