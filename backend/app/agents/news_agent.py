"""Provider-grounded company news retrieval and digest creation."""

import asyncio

from app.agents.knowledge_support import citations_from, insights_from
from app.agents.models import NewsAgentOutput
from app.knowledge.retriever import KnowledgeRetriever
from app.providers.market_data_provider import MarketDataProvider


class NewsAgent:
    """Fetch recent headlines and create an attributable extractive summary."""

    def __init__(
        self,
        provider: MarketDataProvider,
        limit: int = 5,
        market_ticker: str = "SPY",
        retriever: KnowledgeRetriever | None = None,
        retrieval_limit: int = 3,
    ) -> None:
        self._provider = provider
        self._limit = limit
        self._market_ticker = market_ticker
        self._retriever = retriever
        self._retrieval_limit = retrieval_limit

    async def analyze(self, ticker: str) -> NewsAgentOutput:
        knowledge_task = (
            self._retriever.retrieve(
                "earnings call recent events management guidance outlook",
                ticker,
                self._retrieval_limit,
            )
            if self._retriever
            else _empty_chunks()
        )
        company_items, market_items, chunks = await asyncio.gather(
            self._provider.get_company_news(ticker, self._limit),
            self._provider.get_company_news(self._market_ticker, self._limit),
            knowledge_task,
        )
        if not company_items and not market_items:
            return NewsAgentOutput(
                summary=(
                    f"No recent provider-supplied company or market headlines "
                    f"were available for {ticker}."
                ),
                headlines=(),
                document_insights=insights_from(chunks),
                citations=citations_from(chunks),
            )
        headlines = tuple(
            item.headline for item in (*company_items, *market_items)
        )
        company_digest = "; ".join(
            f"{item.headline} ({item.publisher})" for item in company_items
        ) or "none available"
        market_digest = "; ".join(
            f"{item.headline} ({item.publisher})" for item in market_items
        ) or "none available"
        document_digest = (
            f" Document context: {chunks[0].text[:240]}"
            if chunks
            else ""
        )
        return NewsAgentOutput(
            summary=(
                f"Recent {ticker} coverage: {company_digest}. Broad-market "
                f"coverage: {market_digest}.{document_digest}"
            ),
            headlines=headlines,
            document_insights=insights_from(chunks),
            citations=citations_from(chunks),
        )


async def _empty_chunks() -> list:
    return []
