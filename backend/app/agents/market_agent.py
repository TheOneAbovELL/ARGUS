"""Explainable interpretation of market and quant data."""

from app.agents.models import MarketAgentOutput
from app.agents.knowledge_support import citations_from, insights_from
from app.knowledge.retriever import KnowledgeRetriever
from app.services.market_data import CompanyAnalysis


class MarketAgent:
    """Convert company and quant measurements into a market summary."""

    def __init__(
        self,
        retriever: KnowledgeRetriever | None = None,
        retrieval_limit: int = 3,
    ) -> None:
        self._retriever = retriever
        self._retrieval_limit = retrieval_limit

    async def analyze(self, analysis: CompanyAnalysis) -> MarketAgentOutput:
        metrics = analysis.metrics
        if metrics.annual_return >= 0.20:
            trend = "strong positive"
        elif metrics.annual_return >= 0:
            trend = "positive"
        elif metrics.annual_return > -0.20:
            trend = "negative"
        else:
            trend = "strong negative"

        if metrics.volatility < 0.20:
            volatility_band = "low"
        elif metrics.volatility < 0.35:
            volatility_band = "moderate"
        else:
            volatility_band = "high"

        snapshot = analysis.snapshot
        chunks = (
            await self._retriever.retrieve(
                "revenue growth demand business performance management guidance",
                snapshot.ticker,
                self._retrieval_limit,
            )
            if self._retriever
            else []
        )
        evidence_note = (
            f" Document evidence: {chunks[0].text[:240]}"
            if chunks
            else ""
        )
        return MarketAgentOutput(
            summary=(
                f"{snapshot.company_name} ({snapshot.ticker}) trades at "
                f"{snapshot.current_price:.2f}. Its annualized historical return is "
                f"{metrics.annual_return:.1%}, indicating a {trend} trend, with "
                f"{volatility_band} annualized volatility of {metrics.volatility:.1%}."
                f"{evidence_note}"
            ),
            document_insights=insights_from(chunks),
            citations=citations_from(chunks),
        )
