"""Portfolio application service: fetch inputs concurrently, run the pure
engine, and translate engine errors into API-level errors."""

import asyncio
from collections.abc import Sequence

from app.core.errors import InsufficientDataError, InvalidRequestError, SymbolNotFoundError
from app.portfolio.engine import (
    STRESS_EPISODES,
    PortfolioAnalysis,
    PortfolioPosition,
    PortfolioValidationError,
    RebalancingModel,
    StressResult,
    analyze_portfolio,
    stress_test,
    validate_holdings,
)
from app.providers.models import PriceHistory, Provenance, normalize_symbol
from app.quant.metrics import QuantDataError
from app.services.market_data import AnalysisWindow, MarketDataService, default_benchmark_for


class PortfolioService:
    def __init__(self, market_data: MarketDataService, default_benchmark: str = "SPY") -> None:
        self._market = market_data
        self._default_benchmark = default_benchmark

    def _positions(self, holdings: Sequence[tuple[str, float]]) -> list[PortfolioPosition]:
        positions = [PortfolioPosition(normalize_symbol(s), w) for s, w in holdings]
        try:
            validate_holdings(positions)
        except PortfolioValidationError as exc:
            raise InvalidRequestError(str(exc)) from exc
        return positions

    async def _histories(
        self, symbols: Sequence[str], window: AnalysisWindow, benchmark: str
    ) -> tuple[dict[str, PriceHistory], PriceHistory | None]:
        fetched = await asyncio.gather(
            *(self._market.history_or_none(symbol, window) for symbol in symbols),
            self._market.history_or_none(benchmark, window),
        )
        histories = {s: h for s, h in zip(symbols, fetched[:-1]) if h is not None}
        missing = [s for s in symbols if s not in histories]
        if missing:
            raise SymbolNotFoundError(
                f"No price history in the selected window for: {', '.join(missing)}.",
                details={"symbols": missing},
            )
        return histories, fetched[-1]

    async def analyze(
        self,
        holdings: Sequence[tuple[str, float]],
        window: AnalysisWindow,
        model: RebalancingModel,
        benchmark: str | None = None,
        risk_free_rate: float = 0.0,
    ) -> tuple[PortfolioAnalysis, dict[str, Provenance]]:
        positions = self._positions(holdings)
        benchmark_symbol = normalize_symbol(
            benchmark or default_benchmark_for([p.ticker for p in positions], self._default_benchmark)
        )
        histories, bench = await self._histories([p.ticker for p in positions], window, benchmark_symbol)
        try:
            analysis = analyze_portfolio(
                positions,
                histories,
                bench,
                benchmark_symbol,
                model,
                risk_free_rate,
                None if window.label == "max" else window.start,
            )
        except PortfolioValidationError as exc:
            raise InvalidRequestError(str(exc)) from exc
        except QuantDataError as exc:
            raise InsufficientDataError(str(exc)) from exc
        provenance = {s: h.provenance for s, h in histories.items()}
        if bench is not None:
            provenance[bench.symbol] = bench.provenance
        return analysis, provenance

    async def stress(
        self,
        holdings: Sequence[tuple[str, float]],
        benchmark: str | None = None,
    ) -> list[StressResult]:
        positions = self._positions(holdings)
        benchmark_symbol = normalize_symbol(
            benchmark or default_benchmark_for([p.ticker for p in positions], self._default_benchmark)
        )
        window = AnalysisWindow(
            start=min(e.start for e in STRESS_EPISODES),
            end=max(e.end for e in STRESS_EPISODES),
            label="stress-episodes",
        )
        fetched = await asyncio.gather(
            *(self._market.history_or_none(p.ticker, window) for p in positions),
            self._market.history_or_none(benchmark_symbol, window),
        )
        histories = {p.ticker: h for p, h in zip(positions, fetched[:-1]) if h is not None}
        return stress_test(positions, histories, fetched[-1])

