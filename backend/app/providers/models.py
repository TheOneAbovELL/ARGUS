"""Provider-independent market-data domain models.

Every payload that originates from an external (or synthetic) source carries a
:class:`Provenance` so the rest of the system — and ultimately the user — can
see where a number came from, when it was retrieved, what moment it describes,
and whether it was served from cache or is stale.
"""

import math
import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from app.core.errors import InvalidRequestError

_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9^][A-Z0-9.\-=^]{0,14}$")


def normalize_symbol(raw: str) -> str:
    """Upper-case and validate a ticker such as ``AAPL``, ``BRK-B``, ``^GSPC``,
    ``BTC-USD``, ``RELIANCE.NS`` or ``EURUSD=X``."""
    symbol = (raw or "").strip().upper()
    if not _SYMBOL_PATTERN.match(symbol):
        raise InvalidRequestError(
            "Symbols must be 1-15 characters using letters, digits, '.', '-', '=' or '^'.",
            details={"symbol": raw},
        )
    return symbol


def is_valid_symbol(raw: str) -> bool:
    return bool(_SYMBOL_PATTERN.match((raw or "").strip().upper()))


class DataMode(StrEnum):
    """How current a piece of market data is — never implied to be real-time."""

    DELAYED = "delayed"  # latest quote from a free source; may lag the exchange
    END_OF_DAY = "end_of_day"  # daily bars; the latest bar may still be forming
    FIXTURE = "fixture"  # deterministic synthetic data, not market prices


@dataclass(frozen=True)
class Provenance:
    provider: str
    mode: DataMode
    retrieved_at: datetime
    as_of: datetime | date | None = None
    cached: bool = False
    stale: bool = False

    def with_cache_state(self, *, cached: bool, stale: bool) -> "Provenance":
        return replace(self, cached=cached, stale=stale)


@dataclass(frozen=True)
class SymbolMatch:
    symbol: str
    name: str
    exchange: str | None = None
    quote_type: str | None = None


@dataclass(frozen=True)
class Quote:
    symbol: str
    name: str
    price: float
    currency: str | None
    provenance: Provenance
    previous_close: float | None = None
    exchange: str | None = None
    quote_type: str | None = None
    market_state: str | None = None

    @property
    def change(self) -> float | None:
        if self.previous_close is None:
            return None
        return self.price - self.previous_close

    @property
    def change_percent(self) -> float | None:
        if not self.previous_close:
            return None
        return self.price / self.previous_close - 1.0


@dataclass(frozen=True)
class KeyStat:
    key: str
    label: str
    value: float | None
    unit: str  # currency | percent (stored as a fraction) | ratio | count
    currency: str | None = None


@dataclass(frozen=True)
class AssetProfile:
    symbol: str
    name: str
    provenance: Provenance
    quote_type: str | None = None
    exchange: str | None = None
    currency: str | None = None
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    website: str | None = None
    summary: str | None = None
    stats: tuple[KeyStat, ...] = ()


@dataclass(frozen=True)
class PriceBar:
    """One daily bar. ``close`` is the traded close (split-adjusted by the
    provider); ``adj_close`` additionally adjusts for dividends and is the
    series used for total-return analytics."""

    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float
    adj_close: float
    volume: int | None = None


@dataclass(frozen=True)
class CorporateAction:
    date: date
    kind: str  # dividend | split
    value: float


@dataclass(frozen=True)
class PriceHistory:
    symbol: str
    currency: str | None
    bars: tuple[PriceBar, ...]
    provenance: Provenance
    actions: tuple[CorporateAction, ...] = ()
    quality_notes: tuple[str, ...] = ()

    @property
    def start(self) -> date:
        return self.bars[0].date

    @property
    def end(self) -> date:
        return self.bars[-1].date

    def adjusted_closes(self) -> dict[date, float]:
        return {bar.date: bar.adj_close for bar in self.bars}


@dataclass(frozen=True)
class NewsItem:
    title: str
    publisher: str
    url: str | None = None
    published_at: datetime | None = None
    related_symbols: tuple[str, ...] = ()
    id: str = ""


@dataclass(frozen=True)
class NewsFeed:
    symbol: str
    items: tuple[NewsItem, ...]
    provenance: Provenance


def clean_bars(raw_bars: list[PriceBar]) -> tuple[tuple[PriceBar, ...], tuple[str, ...]]:
    """Sort, de-duplicate (keep the last bar per date), and drop bars whose
    closes are missing, non-finite, or non-positive. Returns the cleaned bars
    and human-readable notes describing anything that was removed."""
    by_date: dict[date, PriceBar] = {}
    duplicates = 0
    invalid = 0
    for bar in raw_bars:
        if not _positive_finite(bar.close) or not _positive_finite(bar.adj_close):
            invalid += 1
            continue
        if bar.date in by_date:
            duplicates += 1
        by_date[bar.date] = bar
    notes: list[str] = []
    if invalid:
        notes.append(f"Dropped {invalid} bar(s) with missing or non-positive prices.")
    if duplicates:
        notes.append(f"Removed {duplicates} duplicate timestamp(s); kept the latest bar.")
    return tuple(by_date[d] for d in sorted(by_date)), tuple(notes)


def _positive_finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0
