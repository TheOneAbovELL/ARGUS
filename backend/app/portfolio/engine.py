"""Portfolio construction and analytics orchestration."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
import math

from app.providers.market_data_provider import MarketDataProvider, PriceHistory
from app.quant.metrics import QuantDataError, QuantEngine, QuantMetrics


@dataclass(frozen=True)
class PortfolioPosition:
    """A normalized portfolio allocation expressed as a fraction of capital."""

    ticker: str
    weight: float


@dataclass(frozen=True)
class PortfolioResult:
    """Portfolio allocations and their aggregate quantitative metrics."""

    holdings: tuple[PortfolioPosition, ...]
    metrics: QuantMetrics


class PortfolioValidationError(ValueError):
    """Raised when portfolio allocations violate engine invariants."""


class PortfolioEngine:
    """Build a daily-rebalanced portfolio series and analyze it."""

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

    async def analyze(
        self, holdings: Sequence[PortfolioPosition]
    ) -> PortfolioResult:
        """Fetch all histories concurrently and compute portfolio analytics."""
        self._validate_holdings(holdings)
        tickers = [holding.ticker for holding in holdings]
        symbols = list(dict.fromkeys([*tickers, self._benchmark_ticker]))
        histories = await asyncio.gather(
            *(
                self._provider.get_price_history(symbol, self._history_period)
                for symbol in symbols
            )
        )
        history_by_ticker = dict(zip(symbols, histories))
        missing = [symbol for symbol, history in history_by_ticker.items() if history is None]
        if missing:
            raise QuantDataError(
                f"Historical market data is unavailable for: {', '.join(missing)}."
            )

        complete_histories = {
            symbol: history
            for symbol, history in history_by_ticker.items()
            if history is not None
        }
        shared_dates = self._shared_dates(complete_histories)
        prices_by_ticker = {
            symbol: {point.date: point.adjusted_close for point in history.points}
            for symbol, history in complete_histories.items()
        }

        portfolio_values = [1.0]
        for previous_date, current_date in zip(shared_dates, shared_dates[1:]):
            portfolio_return = sum(
                holding.weight
                * (
                    prices_by_ticker[holding.ticker][current_date]
                    / prices_by_ticker[holding.ticker][previous_date]
                    - 1.0
                )
                for holding in holdings
            )
            portfolio_values.append(portfolio_values[-1] * (1.0 + portfolio_return))

        benchmark_prices = [
            prices_by_ticker[self._benchmark_ticker][day] for day in shared_dates
        ]
        metrics = QuantEngine.compute_metrics(
            portfolio_values,
            benchmark_prices,
            self._annual_risk_free_rate,
        )
        return PortfolioResult(tuple(holdings), metrics)

    @staticmethod
    def _validate_holdings(holdings: Sequence[PortfolioPosition]) -> None:
        if not holdings:
            raise PortfolioValidationError("A portfolio must contain at least one holding.")
        tickers = [holding.ticker for holding in holdings]
        if len(tickers) != len(set(tickers)):
            raise PortfolioValidationError("Duplicate ticker symbols are not allowed.")
        if any(
            not holding.ticker
            or not math.isfinite(holding.weight)
            or holding.weight <= 0
            for holding in holdings
        ):
            raise PortfolioValidationError(
                "Every holding requires a ticker and a positive finite weight."
            )
        if not math.isclose(
            sum(holding.weight for holding in holdings),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise PortfolioValidationError("Portfolio weights must sum to 100 percent.")

    @staticmethod
    def _shared_dates(histories: dict[str, PriceHistory]) -> list[date]:
        date_sets = [
            {point.date for point in history.points} for history in histories.values()
        ]
        shared_dates = sorted(set.intersection(*date_sets))
        if len(shared_dates) < 3:
            raise QuantDataError(
                "At least three aligned price observations are required."
            )
        return shared_dates
