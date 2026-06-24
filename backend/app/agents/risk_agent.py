"""Explainable interpretation of quantitative risk metrics."""

from app.agents.knowledge_support import citations_from, insights_from
from app.agents.models import RiskAgentOutput
from app.knowledge.retriever import KnowledgeRetriever
from app.services.market_data import CompanyAnalysis


class RiskAgent:
    """Classify market sensitivity, drawdown, and risk-adjusted performance."""

    def __init__(
        self,
        retriever: KnowledgeRetriever | None = None,
        retrieval_limit: int = 3,
    ) -> None:
        self._retriever = retriever
        self._retrieval_limit = retrieval_limit

    async def analyze(self, analysis: CompanyAnalysis) -> RiskAgentOutput:
        metrics = analysis.metrics
        risks: list[str] = []
        if metrics.beta > 1.2:
            risks.append("above-market sensitivity")
        elif metrics.beta < 0:
            risks.append("historically inverse market exposure")
        if metrics.volatility >= 0.35:
            risks.append("high realized volatility")
        if metrics.max_drawdown <= -0.30:
            risks.append("severe historical drawdown")
        elif metrics.max_drawdown <= -0.15:
            risks.append("material historical drawdown")
        if metrics.sharpe_ratio < 0:
            risks.append("negative historical risk-adjusted return")

        sharpe_quality = (
            "strong" if metrics.sharpe_ratio >= 1 else
            "positive but limited" if metrics.sharpe_ratio >= 0 else
            "negative"
        )
        risk_text = ", ".join(risks) if risks else "no extreme threshold breaches"
        chunks = (
            await self._retriever.retrieve(
                "risk factors competition regulation supply chain liquidity",
                analysis.snapshot.ticker,
                self._retrieval_limit,
            )
            if self._retriever
            else []
        )
        evidence_note = (
            f" Filing risk evidence: {chunks[0].text[:240]}"
            if chunks
            else ""
        )
        return RiskAgentOutput(
            summary=(
                f"Beta is {metrics.beta:.2f}, Sharpe ratio is "
                f"{metrics.sharpe_ratio:.2f} ({sharpe_quality}), and maximum "
                f"drawdown is {metrics.max_drawdown:.1%}. Flags: {risk_text}."
                f"{evidence_note}"
            ),
            risks=tuple(risks),
            document_insights=insights_from(chunks),
            citations=citations_from(chunks),
        )
