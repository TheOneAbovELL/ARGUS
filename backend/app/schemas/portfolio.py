"""Request and response contracts for portfolio analytics."""

import math

from pydantic import BaseModel, Field, field_validator, model_validator


class PortfolioHolding(BaseModel):
    """One long-only portfolio allocation using percentage weight."""

    ticker: str = Field(..., min_length=1, max_length=10)
    weight: float = Field(..., gt=0, le=100)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be blank")
        if not normalized.isalnum():
            raise ValueError("ticker must contain only letters and numbers")
        return normalized


class PortfolioRequest(BaseModel):
    """Validated holdings submitted for portfolio analysis."""

    holdings: list[PortfolioHolding] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_portfolio(self) -> "PortfolioRequest":
        tickers = [holding.ticker for holding in self.holdings]
        if len(tickers) != len(set(tickers)):
            raise ValueError("duplicate ticker symbols are not allowed")
        total_weight = sum(holding.weight for holding in self.holdings)
        if not math.isclose(total_weight, 100.0, rel_tol=0.0, abs_tol=1e-6):
            raise ValueError("portfolio weights must sum to 100")
        return self


class PortfolioMetrics(BaseModel):
    """Aggregate portfolio risk and return metrics."""

    portfolio_return: float
    portfolio_volatility: float
    portfolio_sharpe: float
    portfolio_beta: float
    portfolio_drawdown: float


class PortfolioAnalysisResponse(PortfolioMetrics):
    """Portfolio metrics plus the normalized analyzed allocations."""

    holdings: list[PortfolioHolding]
