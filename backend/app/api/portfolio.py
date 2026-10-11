"""Portfolio analytics (public) and saved portfolios (per user)."""

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import ContainerDep, CurrentUser, DbDep, provider_rate_limit
from app.providers.models import normalize_symbol
from app.repositories.workspace import PortfolioRepository
from app.schemas.common import PageMeta
from app.schemas.portfolio import (
    PortfolioAnalysisOut,
    PortfolioAnalyzeRequest,
    PortfolioIn,
    PortfolioList,
    PortfolioOut,
    PortfolioUpdate,
    StressEpisodeOut,
    StressOut,
    StressRequest,
)
from app.services.market_data import default_benchmark_for

router = APIRouter(prefix="/api", tags=["portfolio"])


@router.post("/portfolio/analyze", response_model=PortfolioAnalysisOut, dependencies=[Depends(provider_rate_limit)])
async def analyze(request: PortfolioAnalyzeRequest, container: ContainerDep):
    window = container.market.window(request.period, request.start, request.end)
    rate = (
        request.risk_free_rate
        if request.risk_free_rate is not None
        else container.settings.quant_annual_risk_free_rate
    )
    benchmark = normalize_symbol(
        request.benchmark
        or default_benchmark_for([h.symbol for h in request.holdings], container.settings.quant_benchmark_ticker)
    )
    analysis, provenance = await container.portfolios.analyze(
        request.fractions(), window, request.model, benchmark, rate
    )
    return PortfolioAnalysisOut.of(analysis, benchmark, rate, provenance)


@router.post("/portfolio/stress", response_model=StressOut, dependencies=[Depends(provider_rate_limit)])
async def stress(request: StressRequest, container: ContainerDep):
    benchmark = normalize_symbol(
        request.benchmark
        or default_benchmark_for([h.symbol for h in request.holdings], container.settings.quant_benchmark_ticker)
    )
    results = await container.portfolios.stress(request.fractions(), benchmark)
    return StressOut(benchmark=benchmark, episodes=[StressEpisodeOut.of(r) for r in results])


@router.get("/portfolios", response_model=PortfolioList)
async def list_portfolios(
    user: CurrentUser,
    db: DbDep,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    page = await PortfolioRepository(db, user.id).list(limit, offset)
    return PortfolioList(
        items=[PortfolioOut.of(p) for p in page.items],
        page=PageMeta(total=page.total, limit=limit, offset=offset),
    )


@router.post("/portfolios", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED)
async def create_portfolio(body: PortfolioIn, user: CurrentUser, db: DbDep, container: ContainerDep):
    portfolio = await PortfolioRepository(db, user.id).create(
        body.name, body.description, _saved_benchmark(body, container), body.rebalancing.value, body.fractions()
    )
    return PortfolioOut.of(portfolio)


@router.get("/portfolios/{portfolio_id}", response_model=PortfolioOut)
async def get_portfolio(portfolio_id: str, user: CurrentUser, db: DbDep):
    return PortfolioOut.of(await PortfolioRepository(db, user.id).get(portfolio_id))


@router.put("/portfolios/{portfolio_id}", response_model=PortfolioOut)
async def update_portfolio(
    portfolio_id: str, body: PortfolioUpdate, user: CurrentUser, db: DbDep, container: ContainerDep
):
    portfolio = await PortfolioRepository(db, user.id).update(
        portfolio_id,
        body.version,
        body.name,
        body.description,
        _saved_benchmark(body, container),
        body.rebalancing.value,
        body.fractions(),
    )
    return PortfolioOut.of(portfolio)


@router.delete("/portfolios/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(portfolio_id: str, user: CurrentUser, db: DbDep) -> Response:
    await PortfolioRepository(db, user.id).delete(portfolio_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _saved_benchmark(body: PortfolioIn, container) -> str:
    """The user's pick, else the market default for these holdings."""
    return body.benchmark or default_benchmark_for(
        [h.symbol for h in body.holdings], container.settings.quant_benchmark_ticker
    )
