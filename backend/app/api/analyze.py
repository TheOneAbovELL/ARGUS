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
async def analyze_ticker(
    request: AnalyzeRequest,
    market_data_service: Annotated[
        MarketDataService, Depends(get_market_data_service)
    ],
) -> AnalyzeResponse:
    """Return a structured market snapshot for a requested ticker."""
    try:
        analysis = await market_data_service.analyze_company(request.ticker)
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
        ticker=analysis.snapshot.ticker,
        company_name=analysis.snapshot.company_name,
        sector=analysis.snapshot.sector,
        current_price=analysis.snapshot.current_price,
        metrics={
            "annual_return": analysis.metrics.annual_return,
            "volatility": analysis.metrics.volatility,
            "sharpe_ratio": analysis.metrics.sharpe_ratio,
            "beta": analysis.metrics.beta,
            "max_drawdown": analysis.metrics.max_drawdown,
        },
    )
