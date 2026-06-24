"""Tests for dependency-aware research coordination."""

import asyncio

from app.agents.coordinator import ResearchCoordinator
from app.agents.models import MarketAgentOutput, NewsAgentOutput, RiskAgentOutput
from app.agents.strategy_agent import StrategyAgent
from tests.test_agents import company_analysis


class ConcurrencyTracker:
    active = 0
    maximum_active = 0

    async def wait(self) -> None:
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1


class DelayedMarketDataService:
    def __init__(self, tracker: ConcurrencyTracker) -> None:
        self.tracker = tracker

    async def analyze_company(self, ticker: str):
        await self.tracker.wait()
        return company_analysis()


class DelayedNewsAgent:
    def __init__(self, tracker: ConcurrencyTracker) -> None:
        self.tracker = tracker

    async def analyze(self, ticker: str) -> NewsAgentOutput:
        await self.tracker.wait()
        return NewsAgentOutput("News digest", ("Headline",))


class DelayedMarketAgent:
    def __init__(self, tracker: ConcurrencyTracker) -> None:
        self.tracker = tracker

    async def analyze(self, analysis) -> MarketAgentOutput:
        await self.tracker.wait()
        return MarketAgentOutput("Market digest")


class DelayedRiskAgent:
    def __init__(self, tracker: ConcurrencyTracker) -> None:
        self.tracker = tracker

    async def analyze(self, analysis) -> RiskAgentOutput:
        await self.tracker.wait()
        return RiskAgentOutput("Risk digest", ("Risk flag",))


def test_coordinator_runs_independent_agents_concurrently() -> None:
    tracker = ConcurrencyTracker()
    coordinator = ResearchCoordinator(
        market_data_service=DelayedMarketDataService(tracker),
        market_agent=DelayedMarketAgent(tracker),
        risk_agent=DelayedRiskAgent(tracker),
        news_agent=DelayedNewsAgent(tracker),
        strategy_agent=StrategyAgent(),
    )

    report = asyncio.run(coordinator.research("NVDA"))

    assert tracker.maximum_active == 2
    assert report.market_summary == "Market digest"
    assert report.risk_summary == "Risk digest"
    assert report.news_summary == "News digest"
    assert "NVDA" in report.bull_case
