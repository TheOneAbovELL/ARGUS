"""Deterministic synthetic market data for offline development and tests.

Every payload is labelled ``DataMode.FIXTURE`` and the provider name says
"synthetic", so the UI can (and does) show that these are **not market
prices**. Real ticker symbols are used only so that workflows such as
portfolio construction are realistic to exercise.

Model: one market factor plus idiosyncratic noise per asset,
``r_i = drift_i + beta_i * r_m + e_i`` on weekdays, with two scripted stress
episodes so historical stress tests have something to measure. Each series is
generated from a fixed origin with a fixed seed, so the value for a given date
never changes as time passes.
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache

import numpy as np

from app.providers.models import (
    AssetProfile,
    DataMode,
    KeyStat,
    NewsFeed,
    NewsItem,
    PriceBar,
    PriceHistory,
    Provenance,
    Quote,
    SymbolMatch,
)

PROVIDER_NAME = "ARGUS fixture data (synthetic)"
_ORIGIN = date(2005, 1, 3)
_TRADING_DAYS = 252


@dataclass(frozen=True)
class _Spec:
    name: str
    quote_type: str
    sector: str | None
    beta: float
    annual_drift: float  # idiosyncratic drift in excess of beta * market
    idio_vol: float
    start_price: float
    currency: str = "USD"


_MARKET = _Spec("SPDR S&P 500 ETF (synthetic)", "ETF", None, 1.0, 0.0, 0.0, 120.0)
_UNIVERSE: dict[str, _Spec] = {
    "SPY": _MARKET,
    "QQQ": _Spec("Invesco QQQ Trust (synthetic)", "ETF", None, 1.15, 0.02, 0.06, 40.0),
    "IWM": _Spec("iShares Russell 2000 ETF (synthetic)", "ETF", None, 1.2, -0.01, 0.08, 60.0),
    "TLT": _Spec("iShares 20+ Year Treasury ETF (synthetic)", "ETF", None, -0.25, 0.03, 0.12, 90.0),
    "GLD": _Spec("SPDR Gold Shares (synthetic)", "ETF", None, 0.05, 0.05, 0.15, 45.0),
    "AAPL": _Spec("Apple Inc. (synthetic)", "EQUITY", "Technology", 1.2, 0.10, 0.22, 12.0),
    "MSFT": _Spec("Microsoft Corporation (synthetic)", "EQUITY", "Technology", 1.05, 0.07, 0.18, 20.0),
    "NVDA": _Spec("NVIDIA Corporation (synthetic)", "EQUITY", "Technology", 1.7, 0.20, 0.40, 25.0),
    "AMZN": _Spec("Amazon.com, Inc. (synthetic)", "EQUITY", "Consumer Cyclical", 1.25, 0.08, 0.28, 18.0),
    "JPM": _Spec("JPMorgan Chase & Co. (synthetic)", "EQUITY", "Financial Services", 1.15, 0.01, 0.20, 35.0),
    "XOM": _Spec("Exxon Mobil Corporation (synthetic)", "EQUITY", "Energy", 0.85, -0.02, 0.22, 60.0),
    "JNJ": _Spec("Johnson & Johnson (synthetic)", "EQUITY", "Healthcare", 0.6, 0.0, 0.14, 60.0),
    "KO": _Spec("The Coca-Cola Company (synthetic)", "EQUITY", "Consumer Defensive", 0.6, 0.0, 0.13, 20.0),
}

# (start, end, extra annualized market drift) — scripted stress episodes.
_EPISODES = (
    (date(2007, 10, 10), date(2009, 3, 9), -0.65),
    (date(2020, 2, 20), date(2020, 3, 23), -4.5),
    (date(2022, 1, 3), date(2022, 10, 12), -0.15),
)


def _seed(label: str) -> int:
    return int.from_bytes(hashlib.sha256(label.encode()).digest()[:8], "big")


def _business_days(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


@lru_cache(maxsize=4)
def _calendar(until: date) -> tuple[date, ...]:
    return tuple(_business_days(_ORIGIN, until))


@lru_cache(maxsize=8)
def _market_returns(until: date) -> np.ndarray:
    days = _calendar(until)
    rng = np.random.default_rng(_seed("market"))
    daily_vol = 0.17 / np.sqrt(_TRADING_DAYS)
    noise = daily_vol * rng.standard_normal(len(days))
    drift = np.full(len(days), 0.08 / _TRADING_DAYS)
    for start, end, episode_drift in _EPISODES:
        mask = np.array([start <= d <= end for d in days])
        drift[mask] += episode_drift / _TRADING_DAYS
        noise[mask] *= 1.8  # volatility clusters in stress regimes
    return drift + noise


@lru_cache(maxsize=64)
def _series(symbol: str, until: date) -> np.ndarray:
    spec = _UNIVERSE[symbol]
    market = _market_returns(until)
    if spec is _MARKET:
        returns = market
    else:
        rng = np.random.default_rng(_seed(symbol))
        idio = spec.idio_vol / np.sqrt(_TRADING_DAYS) * rng.standard_normal(len(market))
        returns = spec.annual_drift / _TRADING_DAYS + spec.beta * market + idio
    returns = np.clip(returns, -0.5, 0.5)
    return spec.start_price * np.cumprod(1.0 + returns)


class FixtureMarketDataProvider:
    name = PROVIDER_NAME

    def __init__(self, today: date | None = None) -> None:
        self._today = today

    def _until(self) -> date:
        return self._today or datetime.now(UTC).date()

    def _provenance(self, as_of: date | None = None) -> Provenance:
        return Provenance(
            provider=self.name,
            mode=DataMode.FIXTURE,
            retrieved_at=datetime.now(UTC),
            as_of=as_of,
        )

    @staticmethod
    def symbols() -> list[str]:
        return sorted(_UNIVERSE)

    async def search(self, query: str, limit: int = 8) -> list[SymbolMatch]:
        needle = query.strip().lower()
        matches = [
            SymbolMatch(symbol, spec.name, "FIXTURE", spec.quote_type)
            for symbol, spec in sorted(_UNIVERSE.items())
            if needle and (needle in symbol.lower() or needle in spec.name.lower())
        ]
        matches.sort(key=lambda m: (not m.symbol.lower().startswith(needle), m.symbol))
        return matches[:limit]

    async def get_quote(self, symbol: str) -> Quote | None:
        if symbol not in _UNIVERSE:
            return None
        days = _calendar(self._until())
        prices = _series(symbol, self._until())
        spec = _UNIVERSE[symbol]
        return Quote(
            symbol=symbol,
            name=spec.name,
            price=float(prices[-1]),
            previous_close=float(prices[-2]),
            currency=spec.currency,
            exchange="FIXTURE",
            quote_type=spec.quote_type,
            market_state="SYNTHETIC",
            provenance=self._provenance(days[-1]),
        )

    async def get_profile(self, symbol: str) -> AssetProfile | None:
        spec = _UNIVERSE.get(symbol)
        if spec is None:
            return None
        prices = _series(symbol, self._until())[-_TRADING_DAYS:]
        return AssetProfile(
            symbol=symbol,
            name=spec.name,
            quote_type=spec.quote_type,
            exchange="FIXTURE",
            currency=spec.currency,
            sector=spec.sector,
            summary=(
                "Synthetic fixture series generated by ARGUS for offline development. "
                "It is not derived from real market data."
            ),
            stats=(
                KeyStat("high_52w", "52-week high", float(prices.max()), "currency", spec.currency),
                KeyStat("low_52w", "52-week low", float(prices.min()), "currency", spec.currency),
            ),
            provenance=self._provenance(),
        )

    async def get_history(self, symbol: str, start: date, end: date) -> PriceHistory | None:
        spec = _UNIVERSE.get(symbol)
        if spec is None:
            return None
        until = self._until()
        days = _calendar(until)
        prices = _series(symbol, until)
        bars = tuple(
            PriceBar(
                date=day,
                open=float(price),
                high=float(price),
                low=float(price),
                close=float(price),
                adj_close=float(price),
                volume=None,
            )
            for day, price in zip(days, prices)
            if start <= day <= end
        )
        if not bars:
            return None
        return PriceHistory(
            symbol=symbol,
            currency=spec.currency,
            bars=bars,
            quality_notes=("Synthetic fixture series: weekdays only, no exchange holidays.",),
            provenance=self._provenance(bars[-1].date),
        )

    async def get_news(self, symbol: str, limit: int = 8) -> NewsFeed:
        items: tuple[NewsItem, ...] = ()
        if symbol in _UNIVERSE:
            items = (
                NewsItem(
                    id=f"fixture-{symbol.lower()}-1",
                    title=f"[Fixture] Synthetic headline about {symbol} for offline testing",
                    publisher="ARGUS fixture feed",
                    related_symbols=(symbol,),
                ),
            )
        return NewsFeed(symbol, items[:limit], self._provenance())
