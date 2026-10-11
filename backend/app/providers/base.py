"""The market-data provider contract.

Return-value semantics are deliberate:

* ``None`` (or an empty collection) means the provider answered and has no
  data for that request — e.g. an unknown symbol.
* A :class:`~app.core.errors.ProviderError` subclass means the provider could
  not answer (outage, timeout, rate limit). Callers must not treat this as
  "no data".
"""

from datetime import date
from typing import Protocol

from app.providers.models import AssetProfile, NewsFeed, PriceHistory, Quote, SymbolMatch


class MarketDataProvider(Protocol):
    name: str

    async def search(self, query: str, limit: int = 8) -> list[SymbolMatch]: ...

    async def get_quote(self, symbol: str) -> Quote | None: ...

    async def get_profile(self, symbol: str) -> AssetProfile | None: ...

    async def get_history(
        self, symbol: str, start: date, end: date
    ) -> PriceHistory | None: ...

    async def get_news(self, symbol: str, limit: int = 8) -> NewsFeed: ...
