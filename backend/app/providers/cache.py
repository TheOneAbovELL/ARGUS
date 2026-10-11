"""Caching decorator for any :class:`MarketDataProvider`.

Policy
------
* **Fresh hit** (age < TTL): served from memory, provenance marked ``cached``.
* **Expired**: the upstream is called. If it fails with a ``ProviderError``
  and a cached value younger than ``max_stale_seconds`` exists, that value is
  served with provenance marked ``stale`` instead of failing the request.
  Otherwise the error propagates — stale data is never invented.
* **Negative results** (``None`` / empty) are cached for a short TTL so a
  mistyped symbol does not hammer the upstream.
* **Single flight**: concurrent misses for the same key share one upstream
  call, preventing request storms when many widgets load at once.
* Bounded LRU size.

Cache keys include every argument that affects the payload (symbol, date
window, limit). History windows that end before today are immutable and use a
long TTL; windows that include today use a short one because the latest bar
may still be forming.
"""

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from typing import Any

from app.core.errors import ProviderError
from app.providers.base import MarketDataProvider
from app.providers.models import AssetProfile, NewsFeed, PriceHistory, Quote, SymbolMatch


@dataclass(frozen=True)
class CacheTTL:
    search: float = 3600
    quote: float = 60
    profile: float = 6 * 3600
    history_open: float = 15 * 60
    history_closed: float = 24 * 3600
    news: float = 10 * 60
    negative: float = 5 * 60


@dataclass
class _Entry:
    value: Any
    stored_at: float
    ttl: float


class CachingMarketDataProvider:
    def __init__(
        self,
        inner: MarketDataProvider,
        ttl: CacheTTL | None = None,
        max_entries: int = 2_000,
        max_stale_seconds: float = 24 * 3600,
        clock: Callable[[], float] = time.monotonic,
        today: Callable[[], date] = lambda: datetime.now(UTC).date(),
    ) -> None:
        self._inner = inner
        self._ttl = ttl or CacheTTL()
        self._max_entries = max_entries
        self._max_stale = max_stale_seconds
        self._clock = clock
        self._today = today
        self._entries: OrderedDict[tuple, _Entry] = OrderedDict()
        self._inflight: dict[tuple, asyncio.Task] = {}
        self.name = inner.name
        self.stats = {"hits": 0, "misses": 0, "stale_served": 0}

    @property
    def inner(self) -> MarketDataProvider:
        return self._inner

    def clear(self) -> None:
        self._entries.clear()

    async def search(self, query: str, limit: int = 8) -> list[SymbolMatch]:
        key = ("search", query.strip().lower(), limit)
        return await self._get(key, self._ttl.search, lambda: self._inner.search(query, limit))

    async def get_quote(self, symbol: str) -> Quote | None:
        return await self._get(("quote", symbol), self._ttl.quote, lambda: self._inner.get_quote(symbol))

    async def get_profile(self, symbol: str) -> AssetProfile | None:
        return await self._get(
            ("profile", symbol), self._ttl.profile, lambda: self._inner.get_profile(symbol)
        )

    async def get_history(self, symbol: str, start: date, end: date) -> PriceHistory | None:
        ttl = self._ttl.history_closed if end < self._today() else self._ttl.history_open
        return await self._get(
            ("history", symbol, start, end), ttl, lambda: self._inner.get_history(symbol, start, end)
        )

    async def get_news(self, symbol: str, limit: int = 8) -> NewsFeed:
        return await self._get(
            ("news", symbol, limit), self._ttl.news, lambda: self._inner.get_news(symbol, limit)
        )

    # ── core ───────────────────────────────────────────────────────────

    async def _get(self, key: tuple, ttl: float, load: Callable[[], Awaitable[Any]]) -> Any:
        now = self._clock()
        entry = self._entries.get(key)
        if entry is not None and now - entry.stored_at < entry.ttl:
            self._entries.move_to_end(key)
            self.stats["hits"] += 1
            return _mark(entry.value, cached=True, stale=False)

        task = self._inflight.get(key)
        if task is None:
            # The upstream load runs as its own task, so cancelling any one
            # caller (e.g. a client closing an SSE stream) never cancels the
            # fetch other callers are waiting on.
            self.stats["misses"] += 1
            task = asyncio.ensure_future(self._load(key, ttl, load, entry, now))
            self._inflight[key] = task
            task.add_done_callback(lambda _: self._inflight.pop(key, None))
        return await asyncio.shield(task)

    async def _load(
        self, key: tuple, ttl: float, load: Callable[[], Awaitable[Any]], entry: "_Entry | None", now: float
    ) -> Any:
        try:
            value = await load()
        except ProviderError:
            # Never turn an outage into "not found": only real payloads are
            # eligible to be served stale.
            if entry is not None and _has_content(entry.value) and now - entry.stored_at < self._max_stale:
                self.stats["stale_served"] += 1
                return _mark(entry.value, cached=True, stale=True)
            raise
        effective_ttl = ttl if _has_content(value) else min(ttl, self._ttl.negative)
        self._store(key, value, effective_ttl)
        return value

    def _store(self, key: tuple, value: Any, ttl: float) -> None:
        self._entries[key] = _Entry(value, self._clock(), ttl)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)


def _has_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, NewsFeed):
        return bool(value.items)
    if isinstance(value, list):
        return bool(value)
    return True


def _mark(value: Any, *, cached: bool, stale: bool) -> Any:
    provenance = getattr(value, "provenance", None)
    if provenance is None:
        return value
    return replace(value, provenance=provenance.with_cache_state(cached=cached, stale=stale))
