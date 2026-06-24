"""HTTP contracts for coordinated investment research."""

from app.schemas.analysis import AnalyzeRequest
from pydantic import BaseModel


class ResearchRequest(AnalyzeRequest):
    """Validated ticker request for the intelligence engine."""


class DocumentSourceResponse(BaseModel):
    """Traceable source metadata for one retrieved document chunk."""

    title: str
    document_type: str
    source: str
    page_number: int
    chunk_id: str
    score: float


class ResearchResponse(BaseModel):
    """Grounded specialist summaries and balanced strategy scenarios."""

    market_summary: str
    risk_summary: str
    news_summary: str
    bull_case: str
    bear_case: str
    neutral_case: str
    key_risks: list[str]
    key_opportunities: list[str]
    document_insights: list[str]
    sources: list[DocumentSourceResponse]
