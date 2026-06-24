"""API tests for the intelligence engine."""

import pytest
from fastapi.testclient import TestClient

from app.agents.models import DocumentCitation, ResearchReport
from app.dependencies.research import get_research_coordinator
from app.main import app


class StaticResearchCoordinator:
    async def research(self, ticker: str) -> ResearchReport:
        return ResearchReport(
            market_summary=f"Market summary for {ticker}",
            risk_summary="Risk summary",
            news_summary="News summary",
            bull_case="Bull case",
            bear_case="Bear case",
            neutral_case="Neutral case",
            key_risks=("Risk one",),
            key_opportunities=("Opportunity one",),
            document_insights=("Management raised full-year guidance.",),
            sources=(
                DocumentCitation(
                    title="Quarterly Filing",
                    document_type="10-Q",
                    source="sec://nvda/q1",
                    page_number=8,
                    chunk_id="chunk-1",
                    score=0.91,
                ),
            ),
        )


client = TestClient(app)


@pytest.fixture(autouse=True)
def static_coordinator() -> None:
    app.dependency_overrides[get_research_coordinator] = StaticResearchCoordinator
    yield
    app.dependency_overrides.clear()


def test_research_endpoint_returns_agent_outputs() -> None:
    response = client.post("/research", json={"ticker": " nvda "})

    assert response.status_code == 200
    assert response.json() == {
        "market_summary": "Market summary for NVDA",
        "risk_summary": "Risk summary",
        "news_summary": "News summary",
        "bull_case": "Bull case",
        "bear_case": "Bear case",
        "neutral_case": "Neutral case",
        "key_risks": ["Risk one"],
        "key_opportunities": ["Opportunity one"],
        "document_insights": ["Management raised full-year guidance."],
        "sources": [
            {
                "title": "Quarterly Filing",
                "document_type": "10-Q",
                "source": "sec://nvda/q1",
                "page_number": 8,
                "chunk_id": "chunk-1",
                "score": 0.91,
            }
        ],
    }


@pytest.mark.parametrize("ticker", ["", "   ", "NVDA!", "TOO-LONG-TICKER"])
def test_research_endpoint_preserves_ticker_validation(ticker: str) -> None:
    response = client.post("/research", json={"ticker": ticker})
    assert response.status_code == 422
