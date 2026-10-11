"""Portfolio analytics and saved-portfolio contracts.

Weights are accepted as **percentages** (0-100] at the API boundary, matching
how people write allocations, and stored/computed as fractions internally.
"""

import math
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import Portfolio
from app.portfolio.engine import PortfolioAnalysis, RebalancingModel, StressResult
from app.providers.models import Provenance, normalize_symbol
from app.schemas.analysis import AnalysisWindowIn, PerformanceOut, RelativeOut
from app.schemas.common import PageMeta, ProvenanceOut


class HoldingIn(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)
    weight: float = Field(..., gt=0, le=100, description="Percent of capital")

    @field_validator("symbol")
    @classmethod
    def _symbol(cls, value: str) -> str:
        return normalize_symbol(value)


class _HoldingsMixin(BaseModel):
    holdings: list[HoldingIn] = Field(..., min_length=1, max_length=30)

    @model_validator(mode="after")
    def _validate_holdings(self):
        symbols = [h.symbol for h in self.holdings]
        if len(symbols) != len(set(symbols)):
            raise ValueError("duplicate symbols are not allowed")
        total = sum(h.weight for h in self.holdings)
        if not math.isclose(total, 100.0, abs_tol=0.01):
            raise ValueError(f"weights must sum to 100 (got {total:.2f})")
        return self

    def fractions(self) -> list[tuple[str, float]]:
        """Renormalize to exactly 1.0 (absorbs the 0.01 input tolerance)."""
        total = sum(h.weight for h in self.holdings)
        return [(h.symbol, h.weight / total) for h in self.holdings]


class PortfolioAnalyzeRequest(AnalysisWindowIn, _HoldingsMixin):
    model: RebalancingModel = RebalancingModel.DAILY_REBALANCED
    benchmark: str | None = Field(None, max_length=16)
    risk_free_rate: float | None = Field(None, ge=-0.05, le=0.25)


class StressRequest(_HoldingsMixin):
    benchmark: str | None = Field(None, max_length=16)


class AssetContributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    weight: float
    ending_weight: float
    total_return: float
    annualized_return: float | None
    annualized_volatility: float | None
    beta: float | None
    return_contribution: float
    risk_contribution: float | None
    marginal_risk: float | None


class PortfolioSeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dates: list[date]
    cumulative_return: list[float]
    drawdown: list[float]
    benchmark_dates: list[date]
    benchmark_cumulative_return: list[float]
    portfolio_cumulative_on_benchmark_dates: list[float]


class PortfolioAnalysisOut(BaseModel):
    model: RebalancingModel
    benchmark: str
    start: date
    end: date
    periods_per_year: int
    risk_free_rate: float
    performance: PerformanceOut
    relative: RelativeOut | None
    assets: list[AssetContributionOut]
    correlation_symbols: list[str]
    correlation: list[list[float | None]]
    diversification_ratio: float | None
    contribution_method: str
    series: PortfolioSeriesOut
    warnings: list[str]
    assumptions: list[str]
    provenance: dict[str, ProvenanceOut]

    @classmethod
    def of(
        cls,
        analysis: PortfolioAnalysis,
        benchmark: str,
        rate: float,
        provenance: dict[str, Provenance],
    ) -> "PortfolioAnalysisOut":
        return cls(
            model=analysis.model,
            benchmark=benchmark,
            start=analysis.start,
            end=analysis.end,
            periods_per_year=analysis.periods_per_year,
            risk_free_rate=rate,
            performance=PerformanceOut.model_validate(analysis.performance),
            relative=RelativeOut.model_validate(analysis.relative) if analysis.relative else None,
            assets=[AssetContributionOut.model_validate(a) for a in analysis.assets],
            correlation_symbols=list(analysis.correlation_symbols),
            correlation=[list(row) for row in analysis.correlation],
            diversification_ratio=analysis.diversification_ratio,
            contribution_method=analysis.contribution_method,
            series=PortfolioSeriesOut.model_validate(analysis.series),
            warnings=list(analysis.warnings),
            assumptions=list(analysis.assumptions),
            provenance={k: ProvenanceOut.of(v) for k, v in provenance.items()},
        )


class StressEpisodeOut(BaseModel):
    key: str
    name: str
    start: date
    end: date
    description: str
    computable: bool
    portfolio_return: float | None
    benchmark_return: float | None
    portfolio_max_drawdown: float | None
    missing_symbols: list[str]

    @classmethod
    def of(cls, result: StressResult) -> "StressEpisodeOut":
        episode = result.episode
        return cls(
            key=episode.key,
            name=episode.name,
            start=episode.start,
            end=episode.end,
            description=episode.description,
            computable=result.computable,
            portfolio_return=result.portfolio_return,
            benchmark_return=result.benchmark_return,
            portfolio_max_drawdown=result.portfolio_max_drawdown,
            missing_symbols=list(result.missing_symbols),
        )


class StressOut(BaseModel):
    benchmark: str
    episodes: list[StressEpisodeOut]
    method: str = (
        "Buy-and-hold replay of the current weights from each episode start to its end using "
        "dividend-adjusted closes. Episodes are skipped when any holding lacks history."
    )


# ── saved portfolios ──────────────────────────────────────────────────


class PortfolioIn(_HoldingsMixin):
    name: str = Field(..., min_length=1, max_length=80)
    description: str | None = Field(None, max_length=500)
    benchmark: str | None = Field(
        None, max_length=16, description="Omit to use the market default (e.g. ^NSEI for NSE/BSE holdings)."
    )
    rebalancing: RebalancingModel = RebalancingModel.DAILY_REBALANCED

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("benchmark")
    @classmethod
    def _benchmark(cls, value: str | None) -> str | None:
        return normalize_symbol(value) if value else None


class PortfolioUpdate(PortfolioIn):
    version: int = Field(..., ge=1, description="Version you last read (optimistic concurrency).")


class HoldingOut(BaseModel):
    symbol: str
    weight: float  # percent


class PortfolioOut(BaseModel):
    id: str
    name: str
    description: str | None
    benchmark: str
    rebalancing: str
    holdings: list[HoldingOut]
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, portfolio: Portfolio) -> "PortfolioOut":
        return cls(
            id=portfolio.id,
            name=portfolio.name,
            description=portfolio.description,
            benchmark=portfolio.benchmark,
            rebalancing=portfolio.rebalancing,
            holdings=[
                HoldingOut(symbol=h.symbol, weight=round(h.weight * 100, 6)) for h in portfolio.holdings
            ],
            version=portfolio.version,
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at,
        )


class PortfolioList(BaseModel):
    items: list[PortfolioOut]
    page: PageMeta
