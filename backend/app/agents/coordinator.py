"""Dependency-aware orchestration for specialized research agents."""

import asyncio

from app.agents.market_agent import MarketAgent
from app.agents.models import ResearchReport
from app.agents.news_agent import NewsAgent
from app.agents.risk_agent import RiskAgent
from app.agents.strategy_agent import StrategyAgent
from app.providers.market_data_provider import MarketDataProviderUnavailableError
from app.services.market_data import (
    MarketDataNotFoundError,
    MarketDataService,
    MarketDataUnavailableError,
)


class ResearchNotFoundError(Exception):
    """Raised when grounded research inputs do not exist for a ticker."""


class ResearchUnavailableError(Exception):
    """Raised when an external research input is temporarily unavailable."""


class ResearchCoordinator:
    """Execute independent agents concurrently and aggregate their outputs."""

    def __init__(
        self,
        market_data_service: MarketDataService,
        market_agent: MarketAgent,
        risk_agent: RiskAgent,
        news_agent: NewsAgent,
        strategy_agent: StrategyAgent,
    ) -> None:
        self._market_data_service = market_data_service
        self._market_agent = market_agent
        self._risk_agent = risk_agent
        self._news_agent = news_agent
        self._strategy_agent = strategy_agent

    async def research(self, ticker: str) -> ResearchReport:
        """Run the research dependency graph for one ticker."""
        try:
            analysis, news = await asyncio.gather(
                self._market_data_service.analyze_company(ticker),
                self._news_agent.analyze(ticker),
            )
            market, risk = await asyncio.gather(
                self._market_agent.analyze(analysis),
                self._risk_agent.analyze(analysis),
            )
            strategy = await self._strategy_agent.analyze(
                analysis, market, risk, news
            )
        except MarketDataNotFoundError as exc:
            raise ResearchNotFoundError(str(exc)) from exc
        except (MarketDataUnavailableError, MarketDataProviderUnavailableError) as exc:
            raise ResearchUnavailableError(
                "Research inputs are temporarily unavailable. Please try again later."
            ) from exc

        agent_outputs = (market, risk, news, strategy)
        insights = tuple(
            dict.fromkeys(
                insight
                for output in agent_outputs
                for insight in output.document_insights
            )
        )
        citations_by_id = {
            citation.chunk_id: citation
            for output in agent_outputs
            for citation in output.citations
        }
        return ResearchReport(
            market_summary=market.summary,
            risk_summary=risk.summary,
            news_summary=news.summary,
            bull_case=strategy.bull_case,
            bear_case=strategy.bear_case,
            neutral_case=strategy.neutral_case,
            key_risks=strategy.key_risks,
            key_opportunities=strategy.key_opportunities,
            document_insights=insights,
            sources=tuple(citations_by_id.values()),
        )
