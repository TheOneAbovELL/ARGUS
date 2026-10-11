"""Market data and single-asset analytics routes."""

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import ContainerDep, provider_rate_limit
from app.schemas.analysis import AssetAnalysisOut, AssetAnalysisRequest
from app.schemas.market import (
    HistoryOut,
    NewsOut,
    ProfileOut,
    QuoteOut,
    QuoteResultOut,
    SymbolMatchOut,
    TechnicalsOut,
)
from app.services.market_data import default_benchmark_for

router = APIRouter(prefix="/api", tags=["market"], dependencies=[Depends(provider_rate_limit)])


@router.get("/market/search", response_model=list[SymbolMatchOut])
async def search(container: ContainerDep, q: str = Query(..., min_length=1, max_length=64), limit: int = Query(8, ge=1, le=20)):
    matches = await container.market.search(q, limit)
    return [SymbolMatchOut(**vars(m)) for m in matches]


@router.get("/market/quotes", response_model=list[QuoteResultOut])
async def quotes(container: ContainerDep, symbols: str = Query(..., max_length=400, description="Comma-separated")):
    requested = [s for s in symbols.split(",") if s.strip()]
    results = await container.market.quotes(requested)
    return [
        QuoteResultOut(symbol=r.symbol, quote=QuoteOut.of(r.quote) if r.quote else None, error=r.error)
        for r in results
    ]


@router.get("/market/{symbol}/quote", response_model=QuoteOut)
async def quote(symbol: str, container: ContainerDep):
    return QuoteOut.of(await container.market.quote(symbol))


@router.get("/market/{symbol}/profile", response_model=ProfileOut)
async def profile(symbol: str, container: ContainerDep):
    return ProfileOut.of(await container.market.profile(symbol))


@router.get("/market/{symbol}/history", response_model=HistoryOut)
async def history(
    symbol: str,
    container: ContainerDep,
    period: str | None = Query(None),
    start: date | None = None,
    end: date | None = None,
):
    window = container.market.window(period, start, end)
    return HistoryOut.of(await container.market.history(symbol, window))


@router.get("/market/{symbol}/technicals", response_model=TechnicalsOut)
async def technicals(
    symbol: str,
    container: ContainerDep,
    period: str | None = Query(None),
    start: date | None = None,
    end: date | None = None,
):
    """Daily OHLCV with SMA/EMA, Bollinger, RSI, MACD, ATR and an explained
    summary of what each indicator currently reads."""
    window = container.market.window(period, start, end)
    chart = await container.technicals.chart(symbol, window)
    default = default_benchmark_for([chart.symbol], container.settings.quant_benchmark_ticker)
    return TechnicalsOut.of(chart, default)


@router.get("/market/{symbol}/news", response_model=NewsOut)
async def news(symbol: str, container: ContainerDep, limit: int = Query(8, ge=1, le=20)):
    return NewsOut.of(await container.market.news(symbol, limit))


@router.post("/analytics/asset", response_model=AssetAnalysisOut)
async def analyze_asset(request: AssetAnalysisRequest, container: ContainerDep):
    window = container.market.window(request.period, request.start, request.end)
    rate = (
        request.risk_free_rate
        if request.risk_free_rate is not None
        else container.settings.quant_annual_risk_free_rate
    )
    analysis = await container.analytics.analyze_asset(request.symbol, window, request.benchmark, rate)
    return AssetAnalysisOut.of(analysis)
