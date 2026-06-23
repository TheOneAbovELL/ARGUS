"""Tests for the ARGUS ticker analysis endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.dependencies.market_data import get_market_data_service
from app.main import app
from app.providers.market_data_provider import (
    MarketDataProviderUnavailableError,
    MarketDataSnapshot,
    MockMarketDataProvider,
)
from app.services.market_data import MarketDataService


client = TestClient(app)


@pytest.fixture(autouse=True)
def use_mock_market_data_service() -> None:
    """Keep API tests deterministic and independent of Yahoo Finance."""
    app.dependency_overrides[get_market_data_service] = lambda: MarketDataService(
        provider=MockMarketDataProvider()
    )
    yield
    app.dependency_overrides.clear()


class OverrideMarketDataProvider:
    """Provider test double used to verify FastAPI dependency overrides."""

    def get_company_snapshot(self, ticker: str) -> MarketDataSnapshot:
        """Return a distinct snapshot for any valid ticker."""
        return MarketDataSnapshot(
            ticker=ticker,
            company_name="Injected Company",
            sector="Testing",
            current_price=99.99,
        )


class UnavailableMarketDataProvider:
    """Provider test double that simulates an upstream outage."""

    def get_company_snapshot(self, ticker: str) -> None:
        """Raise the provider boundary exception."""
        raise MarketDataProviderUnavailableError("upstream failed")


def test_analyze_endpoint_returns_market_snapshot() -> None:
    """A supported ticker should return the expected structured response."""
    response = client.post("/analyze", json={"ticker": "NVDA"})

    assert response.status_code == 200
    assert response.json() == {
        "ticker": "NVDA",
        "company_name": "NVIDIA Corporation",
        "sector": "Technology",
        "current_price": 182.43,
    }


def test_analyze_endpoint_normalizes_ticker_input() -> None:
    """Ticker input should be stripped and uppercased before service lookup."""
    response = client.post("/analyze", json={"ticker": " nvda "})

    assert response.status_code == 200
    assert response.json()["ticker"] == "NVDA"


def test_analyze_endpoint_rejects_blank_ticker() -> None:
    """Blank ticker input should fail request validation."""
    response = client.post("/analyze", json={"ticker": "   "})

    assert response.status_code == 422


def test_analyze_endpoint_rejects_invalid_ticker_characters() -> None:
    """Ticker input with punctuation should fail request validation."""
    response = client.post("/analyze", json={"ticker": "NVDA!"})

    assert response.status_code == 422


def test_analyze_endpoint_returns_not_found_for_unknown_ticker() -> None:
    """Well-formed but unsupported tickers should return a 404."""
    response = client.post("/analyze", json={"ticker": "MSFT"})

    assert response.status_code == 404
    assert "MSFT" in response.json()["detail"]


def test_analyze_endpoint_uses_injected_market_data_service() -> None:
    """The route should use the service supplied by FastAPI's DI system."""
    app.dependency_overrides[get_market_data_service] = lambda: MarketDataService(
        provider=OverrideMarketDataProvider()
    )

    response = client.post("/analyze", json={"ticker": "MSFT"})

    assert response.status_code == 200
    assert response.json() == {
        "ticker": "MSFT",
        "company_name": "Injected Company",
        "sector": "Testing",
        "current_price": 99.99,
    }


def test_analyze_endpoint_returns_service_unavailable_for_provider_failure() -> None:
    """External provider failures should produce a stable HTTP response."""
    app.dependency_overrides[get_market_data_service] = lambda: MarketDataService(
        provider=UnavailableMarketDataProvider()
    )

    response = client.post("/analyze", json={"ticker": "NVDA"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Market data is temporarily unavailable. Please try again later."
    }
