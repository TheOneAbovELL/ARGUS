"""Market-data response contracts."""

from datetime import date, datetime

from pydantic import BaseModel

from app.providers.models import AssetProfile, NewsFeed, PriceHistory, Quote
from app.schemas.common import ProvenanceOut


class SymbolMatchOut(BaseModel):
    symbol: str
    name: str
    exchange: str | None = None
    quote_type: str | None = None


class QuoteOut(BaseModel):
    symbol: str
    name: str
    price: float
    previous_close: float | None
    change: float | None
    change_percent: float | None
    currency: str | None
    exchange: str | None
    quote_type: str | None
    market_state: str | None
    provenance: ProvenanceOut

    @classmethod
    def of(cls, quote: Quote) -> "QuoteOut":
        return cls(
            symbol=quote.symbol,
            name=quote.name,
            price=quote.price,
            previous_close=quote.previous_close,
            change=quote.change,
            change_percent=quote.change_percent,
            currency=quote.currency,
            exchange=quote.exchange,
            quote_type=quote.quote_type,
            market_state=quote.market_state,
            provenance=ProvenanceOut.of(quote.provenance),
        )


class QuoteResultOut(BaseModel):
    symbol: str
    quote: QuoteOut | None
    error: str | None


class KeyStatOut(BaseModel):
    key: str
    label: str
    value: float | None
    unit: str
    currency: str | None = None


class ProfileOut(BaseModel):
    symbol: str
    name: str
    quote_type: str | None
    exchange: str | None
    currency: str | None
    sector: str | None
    industry: str | None
    country: str | None
    website: str | None
    summary: str | None
    stats: list[KeyStatOut]
    provenance: ProvenanceOut

    @classmethod
    def of(cls, profile: AssetProfile) -> "ProfileOut":
        return cls(
            symbol=profile.symbol,
            name=profile.name,
            quote_type=profile.quote_type,
            exchange=profile.exchange,
            currency=profile.currency,
            sector=profile.sector,
            industry=profile.industry,
            country=profile.country,
            website=profile.website,
            summary=profile.summary,
            stats=[KeyStatOut(**vars(s)) for s in profile.stats],
            provenance=ProvenanceOut.of(profile.provenance),
        )


class CorporateActionOut(BaseModel):
    date: date
    kind: str
    value: float


class HistoryOut(BaseModel):
    """Columnar daily bars (compact for charting)."""

    symbol: str
    currency: str | None
    dates: list[date]
    open: list[float | None]
    high: list[float | None]
    low: list[float | None]
    close: list[float]
    adj_close: list[float]
    volume: list[int | None]
    actions: list[CorporateActionOut]
    quality_notes: list[str]
    provenance: ProvenanceOut

    @classmethod
    def of(cls, history: PriceHistory) -> "HistoryOut":
        bars = history.bars
        return cls(
            symbol=history.symbol,
            currency=history.currency,
            dates=[b.date for b in bars],
            open=[b.open for b in bars],
            high=[b.high for b in bars],
            low=[b.low for b in bars],
            close=[b.close for b in bars],
            adj_close=[b.adj_close for b in bars],
            volume=[b.volume for b in bars],
            actions=[CorporateActionOut(**vars(a)) for a in history.actions],
            quality_notes=list(history.quality_notes),
            provenance=ProvenanceOut.of(history.provenance),
        )


class NewsItemOut(BaseModel):
    id: str
    title: str
    publisher: str
    url: str | None
    published_at: datetime | None
    related_symbols: list[str]


class NewsOut(BaseModel):
    symbol: str
    items: list[NewsItemOut]
    provenance: ProvenanceOut

    @classmethod
    def of(cls, feed: NewsFeed) -> "NewsOut":
        return cls(
            symbol=feed.symbol,
            items=[
                NewsItemOut(
                    id=i.id,
                    title=i.title,
                    publisher=i.publisher,
                    url=i.url,
                    published_at=i.published_at,
                    related_symbols=list(i.related_symbols),
                )
                for i in feed.items
            ],
            provenance=ProvenanceOut.of(feed.provenance),
        )


class SignalOut(BaseModel):
    key: str
    label: str
    value: str
    tone: str
    reading: str
    method: str


class TechnicalsOut(BaseModel):
    """Daily bars plus indicators aligned to ``dates`` (``null`` = warm-up)."""

    symbol: str
    currency: str | None
    window: dict
    dates: list[date]
    open: list[float | None]
    high: list[float | None]
    low: list[float | None]
    close: list[float]
    volume: list[int | None]
    indicators: dict[str, list[float | None]]
    signals: list[SignalOut]
    high_52w: float | None
    low_52w: float | None
    last_close: float
    as_of: date
    default_benchmark: str
    quality_notes: list[str]
    provenance: ProvenanceOut
    conventions: str = (
        "Indicators use traded (split-adjusted) closes, as charting platforms do. Readings describe "
        "common technical-analysis conventions; they are not forecasts or recommendations."
    )

    @classmethod
    def of(cls, chart, default_benchmark: str) -> "TechnicalsOut":
        return cls(
            symbol=chart.symbol,
            currency=chart.currency,
            window={"start": chart.window.start, "end": chart.window.end, "label": chart.window.label},
            dates=chart.dates,
            open=chart.open,
            high=chart.high,
            low=chart.low,
            close=chart.close,
            volume=chart.volume,
            indicators=chart.indicators,
            signals=[SignalOut(**vars(s)) for s in chart.signals],
            high_52w=chart.high_52w,
            low_52w=chart.low_52w,
            last_close=chart.last_close,
            as_of=chart.as_of,
            default_benchmark=default_benchmark,
            quality_notes=chart.quality_notes,
            provenance=ProvenanceOut.of(chart.provenance),
        )
