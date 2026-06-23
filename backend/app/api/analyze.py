"""Ticker analysis route for the ARGUS backend."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.market_data import get_market_data_service
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.market_data import (
    MarketDataNotFoundError,
    MarketDataService,
    MarketDataUnavailableError,
)

router = APIRouter(tags=["analysis"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
)
def analyze_ticker(
    request: AnalyzeRequest,
    market_data_service: Annotated[
        MarketDataService, Depends(get_market_data_service)
    ],
) -> AnalyzeResponse:
    """Return a structured market snapshot for a requested ticker."""
    try:
        snapshot = market_data_service.get_company_snapshot(request.ticker)
    except MarketDataNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except MarketDataUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return AnalyzeResponse(
        ticker=snapshot.ticker,
        company_name=snapshot.company_name,
        sector=snapshot.sector,
        current_price=snapshot.current_price,
    )
