"""Coordinated research API route."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.coordinator import (
    ResearchCoordinator,
    ResearchNotFoundError,
    ResearchUnavailableError,
)
from app.dependencies.research import get_research_coordinator
from app.schemas.research import ResearchRequest, ResearchResponse

router = APIRouter(tags=["research"])


@router.post(
    "/research",
    response_model=ResearchResponse,
    status_code=status.HTTP_200_OK,
)
async def research_ticker(
    request: ResearchRequest,
    coordinator: Annotated[
        ResearchCoordinator, Depends(get_research_coordinator)
    ],
) -> ResearchResponse:
    """Return grounded quantitative research for one ticker."""
    try:
        report = await coordinator.research(request.ticker)
    except ResearchNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ResearchUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return ResearchResponse(
        market_summary=report.market_summary,
        risk_summary=report.risk_summary,
        news_summary=report.news_summary,
        bull_case=report.bull_case,
        bear_case=report.bear_case,
        neutral_case=report.neutral_case,
        key_risks=list(report.key_risks),
        key_opportunities=list(report.key_opportunities),
        document_insights=list(report.document_insights),
        sources=[
            {
                "title": citation.title,
                "document_type": citation.document_type,
                "source": citation.source,
                "page_number": citation.page_number,
                "chunk_id": citation.chunk_id,
                "score": citation.score,
            }
            for citation in report.sources
        ],
    )
