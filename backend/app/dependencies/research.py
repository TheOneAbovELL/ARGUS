"""Dependency wiring for the intelligence engine."""

from app.agents.coordinator import ResearchCoordinator
from app.agents.market_agent import MarketAgent
from app.agents.news_agent import NewsAgent
from app.agents.risk_agent import RiskAgent
from app.agents.strategy_agent import StrategyAgent
from app.core.config import settings
from app.dependencies.market_data import get_market_data_provider
from app.dependencies.knowledge import get_knowledge_retriever
from app.quant.metrics import QuantEngine
from app.services.market_data import MarketDataService


def get_research_coordinator() -> ResearchCoordinator:
    """Provide all research agents with shared grounded dependencies."""
    provider = get_market_data_provider()
    retriever = get_knowledge_retriever()
    quant_engine = QuantEngine(
        provider=provider,
        benchmark_ticker=settings.quant_benchmark_ticker,
        history_period=settings.quant_history_period,
        annual_risk_free_rate=settings.quant_annual_risk_free_rate,
    )
    return ResearchCoordinator(
        market_data_service=MarketDataService(provider, quant_engine),
        market_agent=MarketAgent(
            retriever, settings.knowledge_retrieval_limit
        ),
        risk_agent=RiskAgent(
            retriever, settings.knowledge_retrieval_limit
        ),
        news_agent=NewsAgent(
            provider,
            market_ticker=settings.quant_benchmark_ticker,
            retriever=retriever,
            retrieval_limit=settings.knowledge_retrieval_limit,
        ),
        strategy_agent=StrategyAgent(
            retriever, settings.knowledge_retrieval_limit
        ),
    )
