"""Portfolio analysis HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.portfolio import get_portfolio_service
from app.schemas.portfolio import PortfolioAnalysisResponse, PortfolioRequest
from app.services.portfolio import (
    PortfolioAnalysisError,
    PortfolioRequestError,
    PortfolioService,
    PortfolioUnavailableError,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post(
    "/analyze",
    response_model=PortfolioAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze_portfolio(
    request: PortfolioRequest,
    service: Annotated[PortfolioService, Depends(get_portfolio_service)],
) -> PortfolioAnalysisResponse:
    """Analyze a validated long-only portfolio."""
    try:
        return await service.analyze_portfolio(request.holdings)
    except PortfolioAnalysisError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PortfolioRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except PortfolioUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
