"""Scenario synthesis from grounded specialist-agent outputs."""

from app.agents.models import (
    MarketAgentOutput,
    NewsAgentOutput,
    RiskAgentOutput,
    StrategyAgentOutput,
)
from app.agents.knowledge_support import citations_from, insights_from
from app.knowledge.retriever import KnowledgeRetriever
from app.services.market_data import CompanyAnalysis


class StrategyAgent:
    """Build balanced scenarios without issuing investment instructions."""

    def __init__(
        self,
        retriever: KnowledgeRetriever | None = None,
        retrieval_limit: int = 3,
    ) -> None:
        self._retriever = retriever
        self._retrieval_limit = retrieval_limit

    async def analyze(
        self,
        analysis: CompanyAnalysis,
        market: MarketAgentOutput,
        risk: RiskAgentOutput,
        news: NewsAgentOutput,
    ) -> StrategyAgentOutput:
        metrics = analysis.metrics
        ticker = analysis.snapshot.ticker
        chunks = (
            await self._retriever.retrieve(
                "strategy opportunities competitive advantages capital allocation outlook",
                ticker,
                self._retrieval_limit,
            )
            if self._retriever
            else []
        )
        headline_context = (
            news.headlines[0] if news.headlines else "No recent headline catalyst"
        )
        opportunities = []
        if metrics.annual_return > 0:
            opportunities.append("positive historical return trend")
        if metrics.sharpe_ratio >= 1:
            opportunities.append("strong historical risk-adjusted performance")
        if news.headlines:
            opportunities.append("current company-specific news flow")
        if chunks:
            opportunities.append("document-backed strategic context")
        if not opportunities:
            opportunities.append("potential valuation or operating improvement")

        risks = list(risk.risks) or ["historical metrics may not persist"]
        return StrategyAgentOutput(
            bull_case=(
                f"Bull case for {ticker}: {market.summary} Supporting context: "
                f"{headline_context}."
            ),
            bear_case=(
                f"Bear case for {ticker}: {risk.summary} Adverse market or company "
                "developments could amplify these exposures."
            ),
            neutral_case=(
                f"Neutral case for {ticker}: current quantitative evidence is historical, "
                "while headline and filing effects remain uncertain; monitor new prices "
                "and disclosures."
            ),
            key_risks=tuple(risks),
            key_opportunities=tuple(opportunities),
            document_insights=insights_from(chunks),
            citations=citations_from(chunks),
        )
