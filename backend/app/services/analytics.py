"""Single-asset analytics: fetch inputs, compute deterministic metrics, and
package the series and provenance needed to inspect and chart them."""

import asyncio
from dataclasses import dataclass
from datetime import date

from app.core.errors import InsufficientDataError, InvalidRequestError
from app.providers.models import PriceHistory, Provenance, normalize_symbol
from app.quant.drawdown import drawdown_series
from app.quant.metrics import (
    PerformanceMetrics,
    QuantDataError,
    RelativeMetrics,
    performance_metrics,
    relative_metrics,
)
from app.quant.returns import cumulative_returns, daily_returns, infer_periods_per_year
from app.quant.series import align_on_common_dates, rolling_beta, rolling_volatility
from app.services.market_data import AnalysisWindow, MarketDataService, default_benchmark_for

ROLLING_WINDOW = 63  # ~one quarter of trading days


@dataclass(frozen=True)
class AssetSeries:
    dates: tuple[date, ...]
    close: tuple[float, ...]
    adj_close: tuple[float, ...]
    drawdown: tuple[float, ...]
    rolling_volatility: tuple[float | None, ...]
    daily_returns: tuple[float, ...]


@dataclass(frozen=True)
class ComparisonSeries:
    dates: tuple[date, ...]
    asset_cumulative: tuple[float, ...]
    benchmark_cumulative: tuple[float, ...]
    rolling_beta: tuple[float | None, ...]


@dataclass(frozen=True)
class AssetAnalysis:
    symbol: str
    benchmark: str
    currency: str | None
    benchmark_currency: str | None
    window: AnalysisWindow
    periods_per_year: int
    risk_free_rate: float
    performance: PerformanceMetrics
    relative: RelativeMetrics | None
    series: AssetSeries
    comparison: ComparisonSeries | None
    warnings: tuple[str, ...]
    provenance: dict[str, Provenance]


def _validate_rate(rate: float) -> float:
    if not -0.05 <= rate <= 0.25:
        raise InvalidRequestError("risk_free_rate must be an annual decimal between -0.05 and 0.25.")
    return rate


class AnalyticsService:
    def __init__(self, market_data: MarketDataService, default_benchmark: str = "SPY") -> None:
        self._market = market_data
        self._default_benchmark = default_benchmark

    async def analyze_asset(
        self,
        symbol: str,
        window: AnalysisWindow,
        benchmark: str | None = None,
        risk_free_rate: float = 0.0,
    ) -> AssetAnalysis:
        symbol = normalize_symbol(symbol)
        benchmark_symbol = normalize_symbol(
            benchmark or default_benchmark_for([symbol], self._default_benchmark)
        )
        _validate_rate(risk_free_rate)
        asset_history, benchmark_history = await asyncio.gather(
            self._market.history(symbol, window),
            self._market.history_or_none(benchmark_symbol, window),
        )
        return build_asset_analysis(
            asset_history, benchmark_history, benchmark_symbol, window, risk_free_rate
        )


def build_asset_analysis(
    asset: PriceHistory,
    benchmark: PriceHistory | None,
    benchmark_symbol: str,
    window: AnalysisWindow,
    risk_free_rate: float,
) -> AssetAnalysis:
    """Pure assembly step — separated from I/O so it is directly testable."""
    if len(asset.bars) < 3:
        raise InsufficientDataError(
            f"'{asset.symbol}' has only {len(asset.bars)} price observation(s) in the window; "
            "at least three are required."
        )
    dates = [bar.date for bar in asset.bars]
    adjusted = [bar.adj_close for bar in asset.bars]
    periods = infer_periods_per_year(dates)
    warnings: list[str] = list(asset.quality_notes)

    try:
        performance, perf_warnings = performance_metrics(dates, adjusted, risk_free_rate, periods)
    except QuantDataError as exc:
        raise InsufficientDataError(str(exc)) from exc
    warnings.extend(perf_warnings)

    returns = daily_returns(adjusted)
    series = AssetSeries(
        dates=tuple(dates),
        close=tuple(bar.close for bar in asset.bars),
        adj_close=tuple(adjusted),
        drawdown=tuple(drawdown_series(adjusted)),
        rolling_volatility=tuple([None, *rolling_volatility(returns, ROLLING_WINDOW, periods)]),
        daily_returns=tuple(returns),
    )

    relative: RelativeMetrics | None = None
    comparison: ComparisonSeries | None = None
    provenance = {asset.symbol: asset.provenance}
    if benchmark is None:
        warnings.append(
            f"Benchmark '{benchmark_symbol}' has no history in this window; "
            "relative metrics were not computed."
        )
    else:
        provenance[benchmark.symbol] = benchmark.provenance
        shared, aligned = align_on_common_dates(
            {"asset": asset.adjusted_closes(), "benchmark": benchmark.adjusted_closes()}
        )
        if len(shared) < 3:
            warnings.append("Asset and benchmark share fewer than three dates; relative metrics omitted.")
        else:
            if len(shared) < len(dates) * 0.9:
                warnings.append(
                    f"Only {len(shared)} of {len(dates)} asset dates overlap the benchmark calendar; "
                    "relative metrics use the overlapping dates only."
                )
            if asset.currency and benchmark.currency and asset.currency != benchmark.currency:
                warnings.append(
                    f"{asset.symbol} is priced in {asset.currency} and {benchmark.symbol} in "
                    f"{benchmark.currency}; relative metrics are not FX-adjusted."
                )
            shared_periods = infer_periods_per_year(shared)
            relative, rel_warnings = relative_metrics(
                shared, aligned["asset"], aligned["benchmark"], risk_free_rate, shared_periods
            )
            warnings.extend(rel_warnings)
            comparison = ComparisonSeries(
                dates=tuple(shared),
                asset_cumulative=tuple(cumulative_returns(aligned["asset"])),
                benchmark_cumulative=tuple(cumulative_returns(aligned["benchmark"])),
                rolling_beta=tuple(
                    [None, *rolling_beta(
                        daily_returns(aligned["asset"]),
                        daily_returns(aligned["benchmark"]),
                        ROLLING_WINDOW,
                    )]
                ),
            )

    return AssetAnalysis(
        symbol=asset.symbol,
        benchmark=benchmark_symbol,
        currency=asset.currency,
        benchmark_currency=benchmark.currency if benchmark else None,
        window=window,
        periods_per_year=periods,
        risk_free_rate=risk_free_rate,
        performance=performance,
        relative=relative,
        series=series,
        comparison=comparison,
        warnings=tuple(dict.fromkeys(warnings)),
        provenance=provenance,
    )
