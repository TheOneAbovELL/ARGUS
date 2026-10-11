"""Yahoo Finance adapter (via the community ``yfinance`` library).

Yahoo Finance data is free but unofficial: there is no SLA, quotes may be
delayed, and the endpoints are rate limited. This adapter therefore

* runs blocking ``yfinance`` I/O in worker threads with a global concurrency cap,
* bounds every call with a timeout and retries transient failures with
  exponential backoff and jitter,
* converts "unknown symbol" into ``None`` and transport failures into typed
  :class:`~app.core.errors.ProviderError` subclasses, and
* normalizes units (e.g. ``dividendYield`` is reported in percent).
"""

import asyncio
import hashlib
import logging
import math
import random
import re
import threading
import time
import weakref
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any, TypeVar

import yfinance as yf
from yfinance import exceptions as yf_errors

from app.core.errors import (
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.models import (
    AssetProfile,
    CorporateAction,
    DataMode,
    KeyStat,
    NewsFeed,
    NewsItem,
    PriceBar,
    PriceHistory,
    Provenance,
    Quote,
    SymbolMatch,
    clean_bars,
)

logger = logging.getLogger("argus.providers.yahoo")
T = TypeVar("T")

PROVIDER_NAME = "Yahoo Finance (yfinance)"

_NOT_FOUND_ERRORS: tuple[type[Exception], ...] = (
    yf_errors.YFTickerMissingError,
    yf_errors.YFPricesMissingError,
    yf_errors.YFTzMissingError,
)


class YahooFinanceProvider:
    name = PROVIDER_NAME

    def __init__(
        self,
        timeout_seconds: float = 45.0,
        request_timeout_seconds: float = 12.0,
        max_attempts: int = 3,
        retry_base_seconds: float = 0.4,
        max_concurrency: int = 1,
        ticker_factory: Callable[[str], Any] = yf.Ticker,
        search_factory: Callable[..., Any] = yf.Search,
        sleeper: Callable[[float], None] | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout = timeout_seconds
        self._request_timeout = request_timeout_seconds
        self._max_attempts = max_attempts
        self._retry_base = retry_base_seconds
        self._max_concurrency = max_concurrency
        self._slots = threading.BoundedSemaphore(max_concurrency)
        self._gates: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        self._queue_timeout = timeout_seconds * 3
        self._ticker_factory = ticker_factory
        self._search_factory = search_factory
        self._sleep = sleeper or time.sleep
        self._now = now
        # By default yfinance logs transport failures and returns an empty
        # frame, which is indistinguishable from "no data for this symbol".
        # Make it raise so outages are reported as outages.
        yf.config.debug.hide_exceptions = False

    # ── public contract ────────────────────────────────────────────────

    async def search(self, query: str, limit: int = 8) -> list[SymbolMatch]:
        return await self._run("search", self._search_sync, query, limit)

    async def get_quote(self, symbol: str) -> Quote | None:
        return await self._run("quote", self._quote_sync, symbol)

    async def get_profile(self, symbol: str) -> AssetProfile | None:
        return await self._run("profile", self._profile_sync, symbol)

    async def get_history(self, symbol: str, start: date, end: date) -> PriceHistory | None:
        return await self._run("history", self._history_sync, symbol, start, end)

    async def get_news(self, symbol: str, limit: int = 8) -> NewsFeed:
        return await self._run("news", self._news_sync, symbol, limit)

    # ── execution policy ───────────────────────────────────────────────

    def _gate(self) -> asyncio.Semaphore:
        """Event-loop-level queue: waiting callers don't occupy worker threads
        (which Chroma, PDF parsing, and the DB also need)."""
        loop = asyncio.get_running_loop()
        gate = self._gates.get(loop)
        if gate is None:
            gate = self._gates[loop] = asyncio.Semaphore(self._max_concurrency)
        return gate

    async def _run(self, operation: str, fn: Callable[..., T], *args: Any) -> T:
        gate = self._gate()
        try:
            await asyncio.wait_for(gate.acquire(), timeout=self._queue_timeout)
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                "Yahoo Finance requests are queued behind other work; try again shortly."
            ) from exc
        try:
            # The time budget starts when it is this call's turn, so a burst
            # (e.g. a 30-holding portfolio) completes instead of timing out
            # while queued.
            deadline = time.monotonic() + self._timeout
            return await asyncio.wait_for(
                asyncio.to_thread(self._with_retries, operation, deadline, fn, *args),
                timeout=self._timeout,
            )
        except TimeoutError as exc:
            # The worker thread cannot be cancelled, but it observes the same
            # deadline and stops retrying (and frees its slot) once it passes.
            raise ProviderTimeoutError(
                f"Yahoo Finance did not respond within {self._timeout:.0f}s ({operation})."
            ) from exc
        finally:
            gate.release()

    def _with_retries(self, operation: str, deadline: float, fn: Callable[..., T], *args: Any) -> T:
        last_error: Exception | None = None
        rate_limited = False
        not_found_signals = 0
        for attempt in range(1, self._max_attempts + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self._slots.acquire(timeout=remaining):
                raise ProviderTimeoutError(
                    f"Yahoo Finance did not respond within {self._timeout:.0f}s ({operation})."
                ) from last_error
            try:
                return fn(*args)
            except _NOT_FOUND_ERRORS as exc:
                # yfinance also reports "missing" when a timezone/metadata lookup
                # fails transiently, so require the signal twice before
                # concluding the symbol has no data.
                not_found_signals += 1
                last_error = exc
                if not_found_signals >= 2 or attempt == self._max_attempts:
                    return self._empty_result(operation, args)
                continue
            except yf_errors.YFRateLimitError as exc:
                last_error, rate_limited = exc, True
            except Exception as exc:  # yfinance surfaces many transport errors
                status = http_status(exc)
                if status == 404:
                    # Yahoo answered "no such symbol" (e.g. quoteSummary for a
                    # typo): definitive, so no retry and not an outage.
                    return self._empty_result(operation, args)
                if status == 429:
                    rate_limited = True
                last_error = exc
            finally:
                self._slots.release()
            if attempt < self._max_attempts and deadline - time.monotonic() > 0:
                delay = self._retry_base * (2 ** (attempt - 1))
                self._sleep(delay + random.uniform(0, delay / 2))
        logger.warning(
            "yahoo request failed",
            extra={"operation": operation, "attempts": self._max_attempts, "error": repr(last_error)},
        )
        if rate_limited:
            raise ProviderRateLimitedError(
                "Yahoo Finance is rate limiting requests. Please retry in a minute."
            ) from last_error
        raise ProviderUnavailableError(
            "Yahoo Finance is temporarily unavailable. Please try again later."
        ) from last_error

    def _empty_result(self, operation: str, args: tuple[Any, ...]) -> Any:
        if operation == "search":
            return []
        if operation == "news":
            return NewsFeed(args[0], (), self._provenance(DataMode.DELAYED))
        return None

    def _provenance(self, mode: DataMode, as_of: datetime | date | None = None) -> Provenance:
        return Provenance(provider=self.name, mode=mode, retrieved_at=self._now(), as_of=as_of)

    # ── sync implementations (run in worker threads) ───────────────────

    def _search_sync(self, query: str, limit: int) -> list[SymbolMatch]:
        result = self._search_factory(query, max_results=limit, news_count=0)
        matches: list[SymbolMatch] = []
        for raw in getattr(result, "quotes", None) or []:
            symbol = raw.get("symbol")
            if not symbol:
                continue
            matches.append(
                SymbolMatch(
                    symbol=symbol,
                    name=raw.get("longname") or raw.get("shortname") or symbol,
                    exchange=raw.get("exchDisp") or raw.get("exchange"),
                    quote_type=raw.get("quoteType"),
                )
            )
        return matches[:limit]

    def _info(self, symbol: str) -> dict[str, Any]:
        info = self._ticker_factory(symbol).info
        return info if isinstance(info, dict) else {}

    def _quote_sync(self, symbol: str) -> Quote | None:
        return quote_from_info(symbol, self._info(symbol), self._provenance)

    def _profile_sync(self, symbol: str) -> AssetProfile | None:
        return profile_from_info(symbol, self._info(symbol), self._provenance)

    def _history_sync(self, symbol: str, start: date, end: date) -> PriceHistory | None:
        ticker = self._ticker_factory(symbol)
        frame = ticker.history(
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),  # yfinance's end is exclusive
            interval="1d",
            auto_adjust=False,
            actions=True,
            timeout=self._request_timeout,
        )
        if frame is None or getattr(frame, "empty", True) or "Close" not in frame:
            return None
        metadata = getattr(ticker, "history_metadata", None) or {}
        return history_from_frame(symbol, frame, metadata.get("currency"), self._provenance)

    def _news_sync(self, symbol: str, limit: int) -> NewsFeed:
        raw_items: list[dict[str, Any]] = []
        try:
            raw_items = list(getattr(self._search_factory(symbol, max_results=1, news_count=limit), "news", None) or [])
        except Exception:  # fall back to the per-ticker endpoint below
            raw_items = []
        if not raw_items:
            raw_items = list(self._ticker_factory(symbol).get_news(count=limit) or [])
        items = [item for item in (news_from_raw(raw) for raw in raw_items) if item]
        if not items and "." in symbol:
            items = self._news_by_alias(symbol, limit)
        return NewsFeed(symbol, tuple(items[:limit]), self._provenance(DataMode.DELAYED))

    def _news_by_alias(self, symbol: str, limit: int) -> list[NewsItem]:
        """Yahoo's news search returns nothing for exchange-suffixed symbols
        (``TCS.NS``, ``RELIANCE.NS``) but does for the base symbol or company
        name. Only articles the provider tagged with the *exact* requested
        symbol are kept: a bare base symbol can belong to an unrelated listing
        (e.g. ``TCS`` is also a US ticker)."""
        base = symbol.split(".", 1)[0]
        queries = [base]
        short_name: str | None = None
        try:
            info = self._info(symbol)
            name = info.get("longName") or info.get("shortName")
            if isinstance(name, str) and name.strip():
                queries.append(name.strip())
                short_name = company_short_name(name)
        except Exception:  # the name query is a best-effort extra
            pass
        found: dict[str, NewsItem] = {}
        for query in queries:
            try:
                raw = getattr(self._search_factory(query, max_results=1, news_count=limit * 2), "news", None) or []
            except Exception:
                continue
            for item in (news_from_raw(r) for r in raw):
                if item is None:
                    continue
                # Exact tag, or (for companies Yahoo tags only by their foreign
                # listing, e.g. HDFC Bank -> HDB) a headline naming the company.
                # The latter stay untagged, so reports label them as such.
                named = short_name is not None and short_name.lower() in item.title.lower()
                if symbol in item.related_symbols or named:
                    found.setdefault(item.id, item)
            if len(found) >= limit:
                break
        return sorted(
            found.values(),
            key=lambda i: i.published_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )[:limit]


# ── pure translation helpers (unit-tested without network) ─────────────


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def quote_from_info(
    symbol: str, info: dict[str, Any], provenance: Callable[..., Provenance]
) -> Quote | None:
    price = _num(info.get("regularMarketPrice")) or _num(info.get("currentPrice"))
    if price is None or price <= 0:
        return None
    market_time = info.get("regularMarketTime")
    as_of = (
        datetime.fromtimestamp(market_time, UTC)
        if isinstance(market_time, (int, float)) and market_time > 0
        else None
    )
    return Quote(
        symbol=symbol,
        name=info.get("longName") or info.get("shortName") or symbol,
        price=price,
        currency=info.get("currency"),
        previous_close=_num(info.get("regularMarketPreviousClose")) or _num(info.get("previousClose")),
        exchange=info.get("fullExchangeName") or info.get("exchange"),
        quote_type=info.get("quoteType"),
        market_state=info.get("marketState"),
        provenance=provenance(DataMode.DELAYED, as_of),
    )


def profile_from_info(
    symbol: str, info: dict[str, Any], provenance: Callable[..., Provenance]
) -> AssetProfile | None:
    if not info or not (info.get("longName") or info.get("shortName") or info.get("quoteType")):
        return None
    currency = info.get("currency")
    financial_currency = info.get("financialCurrency") or currency
    dividend_yield = _num(info.get("dividendYield"))
    if dividend_yield is not None:
        # yfinance >= 0.2.54 reports dividendYield in percent (0.73 == 0.73%).
        dividend_yield /= 100.0

    def stat(key: str, label: str, value: Any, unit: str, ccy: str | None = None) -> KeyStat:
        return KeyStat(key, label, _num(value), unit, ccy)

    stats = (
        stat("market_cap", "Market cap", info.get("marketCap"), "currency", currency),
        stat("trailing_pe", "P/E (trailing)", info.get("trailingPE"), "ratio"),
        stat("forward_pe", "P/E (forward)", info.get("forwardPE"), "ratio"),
        stat("price_to_book", "Price / book", info.get("priceToBook"), "ratio"),
        stat("dividend_yield", "Dividend yield", dividend_yield, "percent"),
        stat("revenue", "Revenue (TTM)", info.get("totalRevenue"), "currency", financial_currency),
        stat("revenue_growth", "Revenue growth (YoY)", info.get("revenueGrowth"), "percent"),
        stat("gross_margin", "Gross margin", info.get("grossMargins"), "percent"),
        stat("operating_margin", "Operating margin", info.get("operatingMargins"), "percent"),
        stat("profit_margin", "Profit margin", info.get("profitMargins"), "percent"),
        stat("return_on_equity", "Return on equity", info.get("returnOnEquity"), "percent"),
        stat("free_cash_flow", "Free cash flow", info.get("freeCashflow"), "currency", financial_currency),
        stat("high_52w", "52-week high", info.get("fiftyTwoWeekHigh"), "currency", currency),
        stat("low_52w", "52-week low", info.get("fiftyTwoWeekLow"), "currency", currency),
        stat("avg_volume", "Avg. daily volume", info.get("averageVolume"), "count"),
        stat("shares_outstanding", "Shares outstanding", info.get("sharesOutstanding"), "count"),
        stat("provider_beta", "Beta (provider, 5Y monthly)", info.get("beta"), "ratio"),
    )
    return AssetProfile(
        symbol=symbol,
        name=info.get("longName") or info.get("shortName") or symbol,
        quote_type=info.get("quoteType"),
        exchange=info.get("fullExchangeName") or info.get("exchange"),
        currency=currency,
        sector=info.get("sector"),
        industry=info.get("industry"),
        country=info.get("country"),
        website=info.get("website"),
        summary=info.get("longBusinessSummary"),
        stats=tuple(s for s in stats if s.value is not None),
        provenance=provenance(DataMode.DELAYED),
    )


def history_from_frame(
    symbol: str,
    frame: Any,
    currency: str | None,
    provenance: Callable[..., Provenance],
) -> PriceHistory | None:
    has_adjusted = "Adj Close" in frame
    raw_bars: list[PriceBar] = []
    actions: list[CorporateAction] = []
    for index, row in frame.iterrows():
        day = index.date() if hasattr(index, "date") else index
        close = _num(row.get("Close"))
        adj = _num(row.get("Adj Close")) if has_adjusted else close
        volume = _num(row.get("Volume"))
        raw_bars.append(
            PriceBar(
                date=day,
                open=_num(row.get("Open")),
                high=_num(row.get("High")),
                low=_num(row.get("Low")),
                close=close if close is not None else math.nan,
                adj_close=adj if adj is not None else math.nan,
                volume=int(volume) if volume is not None else None,
            )
        )
        dividend = _num(row.get("Dividends"))
        if dividend:
            actions.append(CorporateAction(day, "dividend", dividend))
        split = _num(row.get("Stock Splits"))
        if split:
            actions.append(CorporateAction(day, "split", split))
    bars, notes = clean_bars(raw_bars)
    if not bars:
        return None
    if not has_adjusted:
        notes += ("Provider returned no dividend-adjusted series; analytics use traded closes.",)
    return PriceHistory(
        symbol=symbol,
        currency=currency,
        bars=bars,
        actions=tuple(actions),
        quality_notes=notes,
        provenance=provenance(DataMode.END_OF_DAY, bars[-1].date),
    )


def news_from_raw(raw: dict[str, Any]) -> NewsItem | None:
    content = raw.get("content") if isinstance(raw.get("content"), dict) else raw
    title = content.get("title")
    if not title:
        return None
    provider = content.get("provider") if isinstance(content.get("provider"), dict) else {}
    canonical = content.get("canonicalUrl") if isinstance(content.get("canonicalUrl"), dict) else {}
    url = canonical.get("url") or content.get("link")
    published: datetime | None = None
    epoch = content.get("providerPublishTime")
    if isinstance(epoch, (int, float)) and epoch > 0:
        published = datetime.fromtimestamp(epoch, UTC)
    elif isinstance(content.get("pubDate"), str):
        try:
            published = datetime.fromisoformat(content["pubDate"].replace("Z", "+00:00"))
        except ValueError:
            published = None
    related = tuple(s.upper() for s in raw.get("relatedTickers") or content.get("relatedTickers") or ())
    identity = raw.get("uuid") or raw.get("id") or url or title
    return NewsItem(
        id=hashlib.sha1(str(identity).encode()).hexdigest()[:12],
        title=title.strip(),
        publisher=provider.get("displayName") or content.get("publisher") or "Unknown publisher",
        url=url if isinstance(url, str) and url.startswith(("http://", "https://")) else None,
        published_at=published,
        related_symbols=related,
    )


def http_status(exc: BaseException) -> int | None:
    """HTTP status carried by a transport exception (requests/curl_cffi style)."""
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


_LEGAL_SUFFIXES = re.compile(
    r"[,.]?\s+(?:limited|ltd|inc|incorporated|corp|corporation|company|co|plc|ag|sa|nv|holdings?)\.?$",
    re.IGNORECASE,
)


def company_short_name(name: str) -> str | None:
    """'HDFC Bank Limited' -> 'HDFC Bank'. Returns None when the result is too
    short to identify a company safely in a headline."""
    short = name.strip()
    while True:
        trimmed = _LEGAL_SUFFIXES.sub("", short).strip()
        if trimmed == short:
            break
        short = trimmed
    return short if len(short) >= 4 else None
