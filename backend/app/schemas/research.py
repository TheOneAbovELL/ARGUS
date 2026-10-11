"""Research request and saved-report contracts."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.agents.models import ResearchReport
from app.db.models import ResearchReport as ResearchRecord
from app.schemas.common import PageMeta


class ResearchRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16, examples=["NVDA"])
    question: str | None = Field(None, max_length=500, examples=["What are the main risks?"])
    period: str = Field("1y", description="Analysis window for the quantitative evidence.")
    save: bool = Field(True, description="Save to research history (signed-in users only).")


class ResearchOut(ResearchReport):
    id: str | None = None
    saved: bool = False


class ResearchSummaryOut(BaseModel):
    id: str
    symbol: str
    name: str | None
    question: str | None
    generation_mode: str
    created_at: datetime
    claims: int

    @classmethod
    def of(cls, record: ResearchRecord) -> "ResearchSummaryOut":
        report = record.report or {}
        claims = sum(len(s.get("claims", [])) for s in report.get("sections", []))
        return cls(
            id=record.id,
            symbol=record.symbol,
            name=report.get("name"),
            question=record.question,
            generation_mode=record.generation_mode,
            created_at=record.created_at,
            claims=claims,
        )


class ResearchList(BaseModel):
    items: list[ResearchSummaryOut]
    page: PageMeta
