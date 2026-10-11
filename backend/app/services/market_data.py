"""Market-data application service: validation, windows, and error semantics.

The service converts provider-level "no data" results into precise domain
errors (unknown symbol vs. insufficient history) and lets provider failures
propagate unchanged so they are reported as outages, not as missing data.
"""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.core.errors import (
    InsufficientDataError,
    InvalidRequestError,
    ProviderError,
    SymbolNotFoundError,
)
from app.providers.base import MarketDataProvider
from app.providers.models import (
    AssetProfile,
    NewsFeed,
    PriceHistory,
    Quote,
    SymbolMatch,
    normalize_symbol,
)

PERIOD_DAYS: dict[str, int] = {
    "1mo": 31,
    "3mo": 92,
    "6mo": 183,
    "1y": 365,
    "2y": 730,
    "3y": 1096,
    "5y": 1827,
    "10y": 3653,
}
SUPPORTED_PERIODS = (*PERIOD_DAYS, "ytd", "max")
_EARLIEST = date(1970, 1, 1)


@dataclass(frozen=True)
class AnalysisWindow:
    """An explicit, reproducible date range. ``label`` records how it was
    requested (e.g. ``1y`` resolved on a given day, or ``custom``)."""

    start: date
    end: date
    label: str


def resolve_window(
    period: str | None = None,
    start: date | None = None,
    end: date | None = None,
    today: date | None = None,
) -> AnalysisWindow:
    today = today or datetime.now(UTC).date()
    if start is not None or end is not None:
        resolved_end = end or today
        if start is None:
            raise InvalidRequestError("A custom window requires a start date.")
        if start >= resolved_end:
            raise InvalidRequestError("The window start must be before its end.")
        if resolved_end > today:
            raise InvalidRequestError("The window cannot end in the future.")
        if start < _EARLIEST:
            raise InvalidRequestError("The window cannot start before 1970-01-01.")
        return AnalysisWindow(start, resolved_end, "custom")

    label = (period or "1y").lower()
    if label == "ytd":
        return AnalysisWindow(date(today.year, 1, 1), today, label)
    if label == "max":
        return AnalysisWindow(_EARLIEST, today, label)
    if label not in PERIOD_DAYS:
        raise InvalidRequestError(
            f"Unsupported period '{period}'. Use one of: {', '.join(SUPPORTED_PERIODS)}."
        )
    return AnalysisWindow(today - timedelta(days=PERIOD_DAYS[label]), today, label)


@dataclass(frozen=True)
class QuoteResult:
    symbol: str
    quote: Quote | None
    error: str | None = None


class MarketDataService:
    def __init__(
        self,
        provider: MarketDataProvider,
        today: Callable[[], date] = lambda: datetime.now(UTC).date(),
    ) -> None:
        self._provider = provider
        self._today = today

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def window(
        self, period: str | None = None, start: date | None = None, end: date | None = None
    ) -> AnalysisWindow:
        return resolve_window(period, start, end, self._today())

    async def search(self, query: str, limit: int = 8) -> list[SymbolMatch]:
        cleaned = query.strip()
        if not 1 <= len(cleaned) <= 64:
            raise InvalidRequestError("Search queries must be 1-64 characters.")
        return await self._provider.search(cleaned, max(1, min(limit, 20)))

    async def quote(self, symbol: str) -> Quote:
        symbol = normalize_symbol(symbol)
        quote = await self._provider.get_quote(symbol)
        if quote is None:
            raise SymbolNotFoundError(f"No quote is available for '{symbol}'.")
        return quote

    async def quotes(self, symbols: list[str]) -> list[QuoteResult]:
        """Best-effort batch: one failing symbol does not fail the batch, and
        each failure is reported explicitly rather than silently omitted."""
        normalized = list(dict.fromkeys(normalize_symbol(s) for s in symbols))
        if len(normalized) > 25:
            raise InvalidRequestError("At most 25 symbols can be quoted at once.")
        results = await asyncio.gather(
            *(self._provider.get_quote(s) for s in normalized), return_exceptions=True
        )
        out: list[QuoteResult] = []
        for symbol, result in zip(normalized, results):
            if isinstance(result, ProviderError):
                out.append(QuoteResult(symbol, None, result.message))
            elif isinstance(result, BaseException):
                raise result
            elif result is None:
                out.append(QuoteResult(symbol, None, "No quote available for this symbol."))
            else:
                out.append(QuoteResult(symbol, result))
        return out

    async def profile(self, symbol: str) -> AssetProfile:
        symbol = normalize_symbol(symbol)
        profile = await self._provider.get_profile(symbol)
        if profile is None:
            raise SymbolNotFoundError(f"No profile is available for '{symbol}'.")
        return profile

    async def history(self, symbol: str, window: AnalysisWindow) -> PriceHistory:
        symbol = normalize_symbol(symbol)
        history = await self._provider.get_history(symbol, window.start, window.end)
        if history is None or not history.bars:
            raise SymbolNotFoundError(
                f"No price history is available for '{symbol}' between "
                f"{window.start.isoformat()} and {window.end.isoformat()}."
            )
        return history

    async def history_or_none(self, symbol: str, window: AnalysisWindow) -> PriceHistory | None:
        try:
            return await self.history(symbol, window)
        except SymbolNotFoundError:
            return None

    async def news(self, symbol: str, limit: int = 8) -> NewsFeed:
        symbol = normalize_symbol(symbol)
        return await self._provider.get_news(symbol, max(1, min(limit, 20)))


def require_observations(history: PriceHistory, minimum: int = 3) -> None:
    if len(history.bars) < minimum:
        raise InsufficientDataError(
            f"'{history.symbol}' has only {len(history.bars)} price observation(s) in the "
            f"selected window; at least {minimum} are required."
        )


# Exchange suffix -> the broad local index used as the default benchmark, so a
# stock is measured against its own market (and currency) unless the user
# chooses otherwise.
LOCAL_BENCHMARKS: dict[tuple[str, ...], str] = {
    (".NS", ".BO"): "^NSEI",  # India: NSE / BSE -> Nifty 50
}


def default_benchmark_for(symbols: Sequence[str], fallback: str) -> str:
    """The local index when every symbol trades on the same mapped market;
    otherwise the configured default (e.g. SPY)."""
    upper = [s.strip().upper() for s in symbols if s and s.strip()]
    for suffixes, index in LOCAL_BENCHMARKS.items():
        if upper and all(s.endswith(suffixes) for s in upper):
            return index
    return fallback
