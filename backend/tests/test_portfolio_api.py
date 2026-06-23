"""API and validation tests for portfolio analytics."""

import pytest
from fastapi.testclient import TestClient

from app.dependencies.portfolio import get_portfolio_service
from app.main import app
from app.portfolio.engine import PortfolioEngine
from app.services.portfolio import PortfolioService
from tests.test_portfolio_engine import DeterministicPortfolioProvider


client = TestClient(app)


@pytest.fixture(autouse=True)
def deterministic_portfolio_service() -> None:
    app.dependency_overrides[get_portfolio_service] = lambda: PortfolioService(
        PortfolioEngine(DeterministicPortfolioProvider())
    )
    yield
    app.dependency_overrides.clear()


def test_portfolio_analyze_returns_metrics_and_normalized_holdings() -> None:
    response = client.post(
        "/portfolio/analyze",
        json={
            "holdings": [
                {"ticker": "nvda", "weight": 40},
                {"ticker": "MSFT", "weight": 30},
                {"ticker": "AAPL", "weight": 30},
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "portfolio_return",
        "portfolio_volatility",
        "portfolio_sharpe",
        "portfolio_beta",
        "portfolio_drawdown",
        "holdings",
    }
    assert payload["holdings"][0] == {"ticker": "NVDA", "weight": 40.0}
    assert payload["portfolio_volatility"] > 0


@pytest.mark.parametrize(
    "holdings",
    [
        [],
        [{"ticker": "NVDA", "weight": 90}],
        [
            {"ticker": "NVDA", "weight": 50},
            {"ticker": "nvda", "weight": 50},
        ],
        [
            {"ticker": "NVDA", "weight": 110},
            {"ticker": "MSFT", "weight": -10},
        ],
        [{"ticker": "NVDA!", "weight": 100}],
    ],
)
def test_portfolio_validation_rejects_invalid_requests(holdings: list[dict]) -> None:
    response = client.post("/portfolio/analyze", json={"holdings": holdings})
    assert response.status_code == 422


def test_portfolio_returns_not_found_for_unknown_ticker() -> None:
    response = client.post(
        "/portfolio/analyze",
        json={"holdings": [{"ticker": "UNKNOWN", "weight": 100}]},
    )
    assert response.status_code == 404
    assert "UNKNOWN" in response.json()["detail"]
