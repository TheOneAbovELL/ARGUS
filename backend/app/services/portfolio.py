"""Application service for portfolio analytics."""

from app.portfolio.engine import (
    PortfolioEngine,
    PortfolioPosition,
    PortfolioValidationError,
)
from app.providers.market_data_provider import MarketDataProviderUnavailableError
from app.quant.metrics import QuantDataError
from app.schemas.portfolio import PortfolioAnalysisResponse, PortfolioHolding


class PortfolioAnalysisError(Exception):
    """Raised when portfolio history cannot support an analysis."""


class PortfolioUnavailableError(Exception):
    """Raised when the external market-data source is unavailable."""


class PortfolioRequestError(Exception):
    """Raised when allocations violate portfolio invariants."""


class PortfolioService:
    """Translate validated holdings and coordinate portfolio analysis."""

    def __init__(self, engine: PortfolioEngine) -> None:
        self._engine = engine

    async def analyze_portfolio(
        self, holdings: list[PortfolioHolding]
    ) -> PortfolioAnalysisResponse:
        positions = [
            PortfolioPosition(holding.ticker, holding.weight / 100.0)
            for holding in holdings
        ]
        try:
            result = await self._engine.analyze(positions)
        except MarketDataProviderUnavailableError as exc:
            raise PortfolioUnavailableError(
                "Portfolio market data is temporarily unavailable. Please try again later."
            ) from exc
        except PortfolioValidationError as exc:
            raise PortfolioRequestError(str(exc)) from exc
        except QuantDataError as exc:
            raise PortfolioAnalysisError(str(exc)) from exc

        return PortfolioAnalysisResponse(
            portfolio_return=result.metrics.annual_return,
            portfolio_volatility=result.metrics.volatility,
            portfolio_sharpe=result.metrics.sharpe_ratio,
            portfolio_beta=result.metrics.beta,
            portfolio_drawdown=result.metrics.max_drawdown,
            holdings=holdings,
        )
