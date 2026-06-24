"""Unit tests for specialist research agents."""

import asyncio

from app.agents.market_agent import MarketAgent
from app.agents.models import NewsAgentOutput
from app.agents.news_agent import NewsAgent
from app.agents.risk_agent import RiskAgent
from app.agents.strategy_agent import StrategyAgent
from app.providers.market_data_provider import MarketDataSnapshot, NewsItem
from app.knowledge.document_loader import DocumentType
from app.knowledge.vector_store import RetrievedChunk
from app.quant.metrics import QuantMetrics
from app.services.market_data import CompanyAnalysis


def company_analysis() -> CompanyAnalysis:
    return CompanyAnalysis(
        snapshot=MarketDataSnapshot("NVDA", "NVIDIA Corporation", "Technology", 200.0),
        metrics=QuantMetrics(0.30, 0.40, 1.20, 1.50, -0.25),
    )


def test_market_agent_explains_metrics_without_recalculating_them() -> None:
    output = asyncio.run(MarketAgent().analyze(company_analysis()))
    assert "30.0%" in output.summary
    assert "high" in output.summary
    assert "200.00" in output.summary


def test_risk_agent_flags_threshold_breaches() -> None:
    output = asyncio.run(RiskAgent().analyze(company_analysis()))
    assert "above-market sensitivity" in output.risks
    assert "high realized volatility" in output.risks
    assert "material historical drawdown" in output.risks


def test_strategy_agent_builds_balanced_grounded_scenarios() -> None:
    analysis = company_analysis()
    market = asyncio.run(MarketAgent().analyze(analysis))
    risk = asyncio.run(RiskAgent().analyze(analysis))
    news = NewsAgentOutput("Recent coverage", ("New product announced",))

    output = asyncio.run(StrategyAgent().analyze(analysis, market, risk, news))

    assert "NVDA" in output.bull_case
    assert "New product announced" in output.bull_case
    assert "NVDA" in output.bear_case
    assert output.key_risks
    assert output.key_opportunities


def test_news_agent_fetches_company_and_market_news_concurrently() -> None:
    class NewsProvider:
        active = 0
        maximum_active = 0

        async def get_company_news(self, ticker: str, limit: int = 5):
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
            await asyncio.sleep(0.01)
            self.active -= 1
            return (NewsItem(f"{ticker} headline", "Test Wire"),)

    provider = NewsProvider()
    output = asyncio.run(NewsAgent(provider).analyze("NVDA"))

    assert output.headlines == ("NVDA headline", "SPY headline")
    assert "Broad-market coverage" in output.summary
    assert provider.maximum_active == 2


def test_all_agents_can_consume_document_context() -> None:
    class StaticRetriever:
        async def retrieve(self, query: str, ticker: str, limit: int = 3):
            return [
                RetrievedChunk(
                    id="chunk-1",
                    text="Management expects data center demand to remain strong.",
                    score=0.91,
                    ticker=ticker,
                    document_type=DocumentType.TEN_Q,
                    title="Quarterly Filing",
                    source="sec://nvda/q1",
                    page_number=8,
                    chunk_index=0,
                )
            ]

    class NewsProvider:
        async def get_company_news(self, ticker: str, limit: int = 5):
            return ()

    retriever = StaticRetriever()
    analysis = company_analysis()
    market = asyncio.run(MarketAgent(retriever).analyze(analysis))
    risk = asyncio.run(RiskAgent(retriever).analyze(analysis))
    news = asyncio.run(NewsAgent(NewsProvider(), retriever=retriever).analyze("NVDA"))
    strategy = asyncio.run(
        StrategyAgent(retriever).analyze(analysis, market, risk, news)
    )

    assert market.citations[0].source == "sec://nvda/q1"
    assert risk.document_insights
    assert news.document_insights
    assert strategy.document_insights
