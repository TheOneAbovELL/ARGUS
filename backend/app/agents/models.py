"""Typed outputs shared by research agents."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentCitation:
    title: str
    document_type: str
    source: str
    page_number: int
    chunk_id: str
    score: float


@dataclass(frozen=True)
class MarketAgentOutput:
    summary: str
    document_insights: tuple[str, ...] = ()
    citations: tuple[DocumentCitation, ...] = ()


@dataclass(frozen=True)
class RiskAgentOutput:
    summary: str
    risks: tuple[str, ...]
    document_insights: tuple[str, ...] = ()
    citations: tuple[DocumentCitation, ...] = ()


@dataclass(frozen=True)
class NewsAgentOutput:
    summary: str
    headlines: tuple[str, ...]
    document_insights: tuple[str, ...] = ()
    citations: tuple[DocumentCitation, ...] = ()


@dataclass(frozen=True)
class StrategyAgentOutput:
    bull_case: str
    bear_case: str
    neutral_case: str
    key_risks: tuple[str, ...]
    key_opportunities: tuple[str, ...]
    document_insights: tuple[str, ...] = ()
    citations: tuple[DocumentCitation, ...] = ()


@dataclass(frozen=True)
class ResearchReport:
    market_summary: str
    risk_summary: str
    news_summary: str
    bull_case: str
    bear_case: str
    neutral_case: str
    key_risks: tuple[str, ...]
    key_opportunities: tuple[str, ...]
    document_insights: tuple[str, ...] = ()
    sources: tuple[DocumentCitation, ...] = ()
