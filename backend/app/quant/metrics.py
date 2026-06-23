"""Quant engine orchestration and aggregate metric model."""

import asyncio
from dataclasses import dataclass

from app.providers.market_data_provider import MarketDataProvider, PriceHistory
from app.quant.beta import beta
from app.quant.drawdown import maximum_drawdown
from app.quant.returns import annual_return, daily_returns
from app.quant.sharpe import sharpe_ratio
from app.quant.volatility import annualized_volatility


@dataclass(frozen=True)
class QuantMetrics:
    """Computed risk and return metrics for one security."""

    annual_return: float
    volatility: float
    sharpe_ratio: float
    beta: float
    max_drawdown: float


class QuantDataError(Exception):
    """Raised when valid market history cannot support the requested metrics."""


class QuantEngine:
    """Fetch historical prices and compute deterministic analytics."""

    def __init__(
        self,
        provider: MarketDataProvider,
        benchmark_ticker: str = "SPY",
        history_period: str = "1y",
        annual_risk_free_rate: float = 0.0,
    ) -> None:
        self._provider = provider
        self._benchmark_ticker = benchmark_ticker
        self._history_period = history_period
        self._annual_risk_free_rate = annual_risk_free_rate

    async def analyze(self, ticker: str) -> QuantMetrics:
        """Fetch asset and benchmark concurrently and aggregate all metrics."""
        asset_history, benchmark_history = await asyncio.gather(
            self._provider.get_price_history(ticker, self._history_period),
            self._provider.get_price_history(
                self._benchmark_ticker, self._history_period
            ),
        )
        if asset_history is None or benchmark_history is None:
            raise QuantDataError("Historical market data is not available.")

        asset_prices, benchmark_prices = self._align_histories(
            asset_history, benchmark_history
        )
        return self.compute_metrics(
            asset_prices,
            benchmark_prices,
            self._annual_risk_free_rate,
        )

    @staticmethod
    def compute_metrics(
        asset_prices: list[float],
        benchmark_prices: list[float],
        annual_risk_free_rate: float = 0.0,
    ) -> QuantMetrics:
        """Compute the shared metric set from aligned price/value series."""
        try:
            asset_returns = daily_returns(asset_prices)
            benchmark_returns = daily_returns(benchmark_prices)
            return QuantMetrics(
                annual_return=annual_return(asset_prices),
                volatility=annualized_volatility(asset_returns),
                sharpe_ratio=sharpe_ratio(
                    asset_returns, annual_risk_free_rate
                ),
                beta=beta(asset_returns, benchmark_returns),
                max_drawdown=maximum_drawdown(asset_prices),
            )
        except ValueError as exc:
            raise QuantDataError(str(exc)) from exc

    @staticmethod
    def _align_histories(
        asset: PriceHistory, benchmark: PriceHistory
    ) -> tuple[list[float], list[float]]:
        asset_by_date = {point.date: point.adjusted_close for point in asset.points}
        benchmark_by_date = {
            point.date: point.adjusted_close for point in benchmark.points
        }
        shared_dates = sorted(asset_by_date.keys() & benchmark_by_date.keys())
        if len(shared_dates) < 3:
            raise QuantDataError(
                "At least three aligned price observations are required."
            )
        return (
            [asset_by_date[date] for date in shared_dates],
            [benchmark_by_date[date] for date in shared_dates],
        )
