"""Single-asset analytics contracts."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ProvenanceOut, WindowOut
from app.services.analytics import AssetAnalysis


class AnalysisWindowIn(BaseModel):
    period: str | None = Field(None, description="1mo, 3mo, 6mo, ytd, 1y, 2y, 3y, 5y, 10y, max")
    start: date | None = None
    end: date | None = None


class AssetAnalysisRequest(AnalysisWindowIn):
    symbol: str = Field(..., min_length=1, max_length=16, examples=["NVDA"])
    benchmark: str | None = Field(None, max_length=16, examples=["SPY"])
    risk_free_rate: float | None = Field(
        None, ge=-0.05, le=0.25, description="Annual decimal rate; defaults to server setting."
    )


class PerformanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    observations: int
    total_return: float
    annualized_return: float | None
    annualized_volatility: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown: float
    max_drawdown_peak: date
    max_drawdown_trough: date
    max_drawdown_recovery: date | None
    longest_drawdown_days: int
    current_drawdown: float
    var_95: float | None
    cvar_95: float | None
    best_period: float
    worst_period: float
    positive_periods_ratio: float


class RelativeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    observations: int
    beta: float | None
    alpha: float | None
    correlation: float | None
    r_squared: float | None
    tracking_error: float | None
    information_ratio: float | None
    benchmark_total_return: float
    benchmark_annualized_return: float | None
    excess_annualized_return: float | None


class AssetSeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dates: list[date]
    close: list[float]
    adj_close: list[float]
    drawdown: list[float]
    rolling_volatility: list[float | None]
    daily_returns: list[float]


class ComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dates: list[date]
    asset_cumulative: list[float]
    benchmark_cumulative: list[float]
    rolling_beta: list[float | None]


class AssetAnalysisOut(BaseModel):
    symbol: str
    benchmark: str
    currency: str | None
    benchmark_currency: str | None
    window: WindowOut
    periods_per_year: int
    risk_free_rate: float
    performance: PerformanceOut
    relative: RelativeOut | None
    series: AssetSeriesOut
    comparison: ComparisonOut | None
    warnings: list[str]
    provenance: dict[str, ProvenanceOut]

    @classmethod
    def of(cls, analysis: AssetAnalysis) -> "AssetAnalysisOut":
        return cls(
            symbol=analysis.symbol,
            benchmark=analysis.benchmark,
            currency=analysis.currency,
            benchmark_currency=analysis.benchmark_currency,
            window=WindowOut.model_validate(analysis.window),
            periods_per_year=analysis.periods_per_year,
            risk_free_rate=analysis.risk_free_rate,
            performance=PerformanceOut.model_validate(analysis.performance),
            relative=RelativeOut.model_validate(analysis.relative) if analysis.relative else None,
            series=AssetSeriesOut.model_validate(analysis.series),
            comparison=ComparisonOut.model_validate(analysis.comparison) if analysis.comparison else None,
            warnings=list(analysis.warnings),
            provenance={k: ProvenanceOut.of(v) for k, v in analysis.provenance.items()},
        )
