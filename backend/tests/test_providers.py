"""Market-data providers, caching policy, and the market service — offline."""

import asyncio
import time
from datetime import UTC, date, datetime

import pandas as pd
import pytest
from yfinance import exceptions as yf_errors

from app.core.errors import (
    InsufficientDataError,
    InvalidRequestError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    SymbolNotFoundError,
)
from app.providers.cache import CacheTTL, CachingMarketDataProvider
from app.providers.fixture import FixtureMarketDataProvider
from app.providers.models import DataMode, PriceBar, Provenance, Quote, clean_bars, normalize_symbol
from app.providers.yahoo import (
    YahooFinanceProvider,
    history_from_frame,
    news_from_raw,
    profile_from_info,
    quote_from_info,
)
from app.services.market_data import MarketDataService, require_observations, resolve_window


def prov(mode=DataMode.DELAYED, as_of=None) -> Provenance:
    return Provenance("test", mode, datetime(2026, 1, 1, tzinfo=UTC), as_of)


# ── symbols & cleaning ────────────────────────────────────────────────


@pytest.mark.parametrize("raw", ["aapl", " BRK-B ", "^GSPC", "BTC-USD", "RELIANCE.NS", "EURUSD=X"])
def test_symbol_normalization_accepts_real_world_tickers(raw: str) -> None:
    assert normalize_symbol(raw) == raw.strip().upper()


@pytest.mark.parametrize("raw", ["", "  ", "NVDA!", "A B", "TOO-LONG-TICKER-X", "../etc"])
def test_symbol_normalization_rejects_garbage(raw: str) -> None:
    with pytest.raises(InvalidRequestError):
        normalize_symbol(raw)


def test_clean_bars_sorts_dedupes_and_drops_invalid() -> None:
    d1, d2, d3 = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    bars, notes = clean_bars([
        PriceBar(d2, None, None, None, 10.0, 10.0),
        PriceBar(d1, None, None, None, 9.0, 9.0),
        PriceBar(d2, None, None, None, 11.0, 11.0),  # duplicate date: keep latest
        PriceBar(d3, None, None, None, -1.0, -1.0),  # invalid
    ])
    assert [(b.date, b.close) for b in bars] == [(d1, 9.0), (d2, 11.0)]
    assert len(notes) == 2


# ── Yahoo translation (pure functions) ────────────────────────────────


def test_quote_from_info_uses_market_time_and_rejects_missing_price() -> None:
    quote = quote_from_info(
        "MSFT",
        {"longName": "Microsoft", "regularMarketPrice": 535.07, "regularMarketPreviousClose": 530.0,
         "regularMarketTime": 1_791_576_001, "currency": "USD", "quoteType": "EQUITY"},
        prov,
    )
    assert quote.price == 535.07 and quote.currency == "USD"
    assert quote.change_percent == pytest.approx(535.07 / 530.0 - 1)
    assert quote.provenance.mode is DataMode.DELAYED
    assert quote.provenance.as_of == datetime.fromtimestamp(1_791_576_001, UTC)
    assert quote_from_info("XXX", {"trailingPegRatio": None}, prov) is None


def test_profile_normalizes_dividend_yield_from_percent() -> None:
    profile = profile_from_info(
        "MSFT",
        {"longName": "Microsoft", "dividendYield": 0.73, "marketCap": 3.9e12, "currency": "USD",
         "trailingPE": 29.1, "beta": float("nan")},
        prov,
    )
    stats = {s.key: s for s in profile.stats}
    assert stats["dividend_yield"].value == pytest.approx(0.0073)
    assert stats["market_cap"].currency == "USD"
    assert "provider_beta" not in stats  # NaN is dropped, not reported as a number


def test_history_from_frame_keeps_traded_and_adjusted_closes_and_actions() -> None:
    index = pd.DatetimeIndex(["2025-01-02", "2025-01-03", "2025-01-03"], tz="America/New_York")
    frame = pd.DataFrame(
        {"Open": [1, 2, 2], "High": [1, 2, 2], "Low": [1, 2, 2], "Close": [10.0, 11.0, 11.5],
         "Adj Close": [9.5, 10.5, 11.0], "Volume": [100, 200, 300], "Dividends": [0, 0.2, 0.2],
         "Stock Splits": [0, 0, 0]},
        index=index,
    )
    history = history_from_frame("TEST", frame, "USD", prov)
    assert [b.close for b in history.bars] == [10.0, 11.5]
    assert [b.adj_close for b in history.bars] == [9.5, 11.0]
    assert history.provenance.mode is DataMode.END_OF_DAY
    assert history.provenance.as_of == date(2025, 1, 3)
    assert any(a.kind == "dividend" for a in history.actions)
    assert any("duplicate" in n for n in history.quality_notes)


def test_news_from_raw_handles_both_response_shapes() -> None:
    flat = news_from_raw({"uuid": "u1", "title": "Headline", "publisher": "Wire",
                          "link": "https://example.com/a", "providerPublishTime": 1_791_652_302,
                          "relatedTickers": ["msft"]})
    nested = news_from_raw({"content": {"title": "Nested", "provider": {"displayName": "Pub"},
                                        "canonicalUrl": {"url": "javascript:alert(1)"},
                                        "pubDate": "2026-10-09T12:00:00Z"}})
    assert flat.related_symbols == ("MSFT",) and flat.url == "https://example.com/a"
    assert nested.publisher == "Pub" and nested.url is None  # non-http URLs are dropped
    assert news_from_raw({"content": {}}) is None


# ── Yahoo execution policy (retries, timeouts, typed errors) ──────────


class FlakyTicker:
    def __init__(self, failures: int, error: Exception) -> None:
        self.failures, self.error, self.calls = failures, error, 0

    @property
    def info(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return {"longName": "Example", "regularMarketPrice": 10.0}


def test_yahoo_retries_transient_errors_with_bounded_attempts() -> None:
    ticker = FlakyTicker(2, ConnectionError("reset"))
    sleeps: list[float] = []
    provider = YahooFinanceProvider(max_attempts=3, ticker_factory=lambda s: ticker, sleeper=sleeps.append)
    quote = asyncio.run(provider.get_quote("EX"))
    assert quote.price == 10.0 and ticker.calls == 3 and len(sleeps) == 2
    assert sleeps[1] > sleeps[0]  # exponential backoff


def test_yahoo_outage_is_an_error_not_an_empty_result() -> None:
    ticker = FlakyTicker(99, ConnectionError("down"))
    provider = YahooFinanceProvider(max_attempts=2, ticker_factory=lambda s: ticker, sleeper=lambda _: None)
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(provider.get_quote("EX"))
    assert ticker.calls == 2


def test_yahoo_rate_limit_maps_to_rate_limited_error() -> None:
    ticker = FlakyTicker(99, yf_errors.YFRateLimitError())
    provider = YahooFinanceProvider(max_attempts=2, ticker_factory=lambda s: ticker, sleeper=lambda _: None)
    with pytest.raises(ProviderRateLimitedError):
        asyncio.run(provider.get_quote("EX"))


def test_yahoo_missing_ticker_needs_two_signals_then_is_none() -> None:
    ticker = FlakyTicker(99, yf_errors.YFTickerMissingError("ZZZ", "no data"))
    provider = YahooFinanceProvider(max_attempts=3, ticker_factory=lambda s: ticker, sleeper=lambda _: None)
    assert asyncio.run(provider.get_quote("ZZZ")) is None
    assert ticker.calls == 2  # confirmed once, not retried to exhaustion


def test_yahoo_transient_missing_signal_recovers() -> None:
    ticker = FlakyTicker(1, yf_errors.YFTzMissingError("AAPL"))  # e.g. tz lookup blip
    provider = YahooFinanceProvider(max_attempts=3, ticker_factory=lambda s: ticker, sleeper=lambda _: None)
    assert asyncio.run(provider.get_quote("AAPL")).price == 10.0


def test_yahoo_is_configured_to_raise_instead_of_returning_empty_data() -> None:
    import yfinance as yf

    YahooFinanceProvider()
    assert yf.config.debug.hide_exceptions is False


def test_yahoo_timeout_is_bounded() -> None:
    class Slow:
        @property
        def info(self):
            time.sleep(0.5)
            return {}

    provider = YahooFinanceProvider(timeout_seconds=0.05, ticker_factory=lambda s: Slow())

    async def call() -> float:
        started = time.perf_counter()
        with pytest.raises(ProviderTimeoutError):
            await provider.get_quote("SLOW")
        return time.perf_counter() - started

    # The caller is released at the timeout even though the worker thread
    # (which cannot be cancelled) keeps running in the background.
    assert asyncio.run(call()) < 0.3


# ── caching policy ────────────────────────────────────────────────────


class CountingProvider:
    name = "counting"

    def __init__(self) -> None:
        self.calls = 0
        self.fail = False
        self.delay = 0.0

    async def get_quote(self, symbol: str):
        self.calls += 1
        await asyncio.sleep(self.delay)
        if self.fail:
            raise ProviderUnavailableError("down")
        if symbol == "NONE":
            return None
        return Quote(symbol, symbol, 1.0, "USD", prov())


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_cache_serves_fresh_hits_and_marks_them_cached() -> None:
    inner, clock = CountingProvider(), Clock()
    cache = CachingMarketDataProvider(inner, CacheTTL(quote=60), clock=clock)
    first = asyncio.run(cache.get_quote("A"))
    second = asyncio.run(cache.get_quote("A"))
    assert inner.calls == 1
    assert first.provenance.cached is False and second.provenance.cached is True


def test_cache_serves_stale_data_on_outage_and_flags_it() -> None:
    inner, clock = CountingProvider(), Clock()
    cache = CachingMarketDataProvider(inner, CacheTTL(quote=60), clock=clock, max_stale_seconds=3600)
    asyncio.run(cache.get_quote("A"))
    clock.now = 120
    inner.fail = True
    stale = asyncio.run(cache.get_quote("A"))
    assert stale.provenance.stale is True
    clock.now = 10_000  # beyond the stale window: the outage surfaces
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(cache.get_quote("A"))


def test_cache_never_turns_an_outage_into_not_found() -> None:
    inner, clock = CountingProvider(), Clock()
    cache = CachingMarketDataProvider(inner, CacheTTL(quote=60, negative=30), clock=clock)
    assert asyncio.run(cache.get_quote("NONE")) is None
    clock.now = 45
    inner.fail = True
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(cache.get_quote("NONE"))


def test_cache_single_flight_collapses_concurrent_misses() -> None:
    inner = CountingProvider()
    inner.delay = 0.02
    cache = CachingMarketDataProvider(inner)

    async def burst():
        return await asyncio.gather(*(cache.get_quote("A") for _ in range(10)))

    results = asyncio.run(burst())
    assert inner.calls == 1 and len(results) == 10


def test_cache_is_bounded() -> None:
    inner = CountingProvider()
    cache = CachingMarketDataProvider(inner, max_entries=3)
    for symbol in "ABCDE":
        asyncio.run(cache.get_quote(symbol))
    asyncio.run(cache.get_quote("A"))  # evicted, refetched
    assert inner.calls == 6


# ── fixture provider & market service ─────────────────────────────────


def test_fixture_provider_is_deterministic_and_labelled() -> None:
    provider = FixtureMarketDataProvider(today=date(2026, 6, 30))
    a = asyncio.run(provider.get_history("AAPL", date(2025, 1, 1), date(2025, 3, 1)))
    b = asyncio.run(FixtureMarketDataProvider(today=date(2026, 9, 30)).get_history("AAPL", date(2025, 1, 1), date(2025, 3, 1)))
    assert [bar.adj_close for bar in a.bars] == [bar.adj_close for bar in b.bars]  # stable as time passes
    assert a.provenance.mode is DataMode.FIXTURE
    assert all(bar.date.weekday() < 5 for bar in a.bars)
    assert asyncio.run(provider.get_history("NOPE", date(2025, 1, 1), date(2025, 3, 1))) is None


def test_resolve_window_periods_and_validation() -> None:
    today = date(2026, 6, 30)
    assert resolve_window("1y", today=today).start == date(2025, 6, 30)
    assert resolve_window("ytd", today=today).start == date(2026, 1, 1)
    custom = resolve_window(start=date(2024, 1, 1), end=date(2024, 6, 1), today=today)
    assert (custom.start, custom.end, custom.label) == (date(2024, 1, 1), date(2024, 6, 1), "custom")
    for bad in ({"period": "7y"}, {"start": date(2026, 1, 1), "end": date(2025, 1, 1)},
                {"start": date(2026, 1, 1), "end": date(2027, 1, 1)}, {"end": date(2026, 1, 1)}):
        with pytest.raises(InvalidRequestError):
            resolve_window(today=today, **bad)


def test_market_service_distinguishes_unknown_symbol_from_outage() -> None:
    service = MarketDataService(FixtureMarketDataProvider(today=date(2026, 6, 30)), today=lambda: date(2026, 6, 30))
    with pytest.raises(SymbolNotFoundError):
        asyncio.run(service.quote("NOPE"))

    class Down(CountingProvider):
        def __init__(self):
            super().__init__()
            self.fail = True

    with pytest.raises(ProviderUnavailableError):
        asyncio.run(MarketDataService(Down()).quote("AAPL"))


def test_batch_quotes_report_partial_failures_explicitly() -> None:
    service = MarketDataService(FixtureMarketDataProvider(today=date(2026, 6, 30)))
    results = asyncio.run(service.quotes(["AAPL", "NOPE", "aapl"]))
    assert [r.symbol for r in results] == ["AAPL", "NOPE"]  # de-duplicated, order kept
    assert results[0].quote is not None and results[1].quote is None and results[1].error


def test_require_observations() -> None:
    history = asyncio.run(FixtureMarketDataProvider(today=date(2026, 6, 30)).get_history("SPY", date(2026, 6, 29), date(2026, 6, 30)))
    with pytest.raises(InsufficientDataError):
        require_observations(history, 3)


def test_abandoned_calls_stop_retrying_and_free_the_slot() -> None:
    class SlowFailing:
        calls = 0

        @property
        def info(self):
            SlowFailing.calls += 1
            time.sleep(0.08)
            raise ConnectionError("stalled")

    provider = YahooFinanceProvider(
        timeout_seconds=0.1, max_attempts=10, max_concurrency=1,
        ticker_factory=lambda s: SlowFailing(), sleeper=lambda _: None,
    )
    with pytest.raises(ProviderTimeoutError):
        asyncio.run(provider.get_quote("SLOW"))
    time.sleep(0.3)  # let the background worker observe the deadline
    assert SlowFailing.calls <= 2  # did not keep retrying to 10 attempts
    assert provider._slots.acquire(timeout=0.01)  # slot was released
    provider._slots.release()


def test_cancelling_one_caller_does_not_cancel_shared_fetch() -> None:
    inner = CountingProvider()
    inner.delay = 0.05
    cache = CachingMarketDataProvider(inner)

    async def scenario():
        first = asyncio.ensure_future(cache.get_quote("A"))
        second = asyncio.ensure_future(cache.get_quote("A"))
        await asyncio.sleep(0.01)
        first.cancel()
        result = await second
        return first.cancelled(), result

    first_cancelled, result = asyncio.run(scenario())
    assert first_cancelled and result.symbol == "A"
    assert inner.calls == 1


def test_queued_calls_get_their_own_budget_and_do_not_hold_threads() -> None:
    class Slowish:
        @property
        def info(self):
            time.sleep(0.05)
            return {"longName": "X", "regularMarketPrice": 1.0}

    provider = YahooFinanceProvider(timeout_seconds=0.12, max_concurrency=1,
                                    ticker_factory=lambda s: Slowish(), sleeper=lambda _: None)

    async def burst():
        return await asyncio.gather(*(provider.get_quote(f"S{i}") for i in range(6)))

    # 6 x 0.05s = 0.3s total > 0.12s budget: succeeds only because budgets
    # start when each call's turn comes.
    assert all(q.price == 1.0 for q in asyncio.run(burst()))


def test_rate_limiter_eviction_never_resets_active_counters() -> None:
    from app.core.errors import RateLimitedError
    from app.core.rate_limit import SlidingWindowRateLimiter

    clock = Clock()
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60, clock=clock, max_keys=10)
    limiter.check("victim")
    limiter.check("victim")
    for i in range(50):  # attacker cycles keys to fill the table
        clock.now += 0.01
        limiter.check(f"noise-{i}")
    clock.now += 0.01
    with pytest.raises(RateLimitedError):
        limiter.check("victim")


class _HTTPError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"HTTP Error {status}: ")
        self.response = type("Response", (), {"status_code": status})()


def test_yahoo_404_is_no_data_without_retry() -> None:
    ticker = FlakyTicker(99, _HTTPError(404))
    provider = YahooFinanceProvider(max_attempts=3, ticker_factory=lambda s: ticker, sleeper=lambda _: None)
    assert asyncio.run(provider.get_quote("ZZZZQ")) is None
    assert ticker.calls == 1


def test_yahoo_http_429_is_rate_limited() -> None:
    ticker = FlakyTicker(99, _HTTPError(429))
    provider = YahooFinanceProvider(max_attempts=2, ticker_factory=lambda s: ticker, sleeper=lambda _: None)
    with pytest.raises(ProviderRateLimitedError):
        asyncio.run(provider.get_quote("EX"))


def test_yahoo_transient_401_is_retried() -> None:
    ticker = FlakyTicker(1, _HTTPError(401))  # e.g. "Invalid Crumb", fixed by retry
    provider = YahooFinanceProvider(max_attempts=3, ticker_factory=lambda s: ticker, sleeper=lambda _: None)
    assert asyncio.run(provider.get_quote("EX")).price == 10.0


def test_suffixed_symbols_fall_back_to_base_and_name_news_with_exact_tagging() -> None:
    """Yahoo returns no news for 'TCS.NS' itself; ARGUS retries with 'TCS' and
    the company name, keeping only articles tagged with exactly 'TCS.NS'."""
    queries: list[str] = []
    articles = {
        "TCS": [
            {"uuid": "a", "title": "TCS wins deal", "publisher": "Wire", "providerPublishTime": 1_791_000_000,
             "relatedTickers": ["TCS.NS", "INFY"]},
            {"uuid": "b", "title": "Container Store news", "publisher": "Wire", "providerPublishTime": 1_791_000_100,
             "relatedTickers": ["TCS"]},  # unrelated US listing: must be dropped
        ],
        "Tata Consultancy Services Limited": [
            {"uuid": "c", "title": "Tata Consultancy Q2 results", "publisher": "Wire",
             "providerPublishTime": 1_791_000_200, "relatedTickers": ["TCS.NS"]},
        ],
    }

    def search(query, max_results, news_count):
        queries.append(query)
        return type("S", (), {"news": articles.get(query, [])})()

    class Ticker:
        info = {"longName": "Tata Consultancy Services Limited"}

        def get_news(self, count):
            return []

    provider = YahooFinanceProvider(ticker_factory=lambda s: Ticker(), search_factory=search, sleeper=lambda _: None)
    feed = asyncio.run(provider.get_news("TCS.NS", 5))
    assert [i.title for i in feed.items] == ["Tata Consultancy Q2 results", "TCS wins deal"]  # newest first
    assert queries[:3] == ["TCS.NS", "TCS", "Tata Consultancy Services Limited"]


def test_company_named_headlines_count_when_yahoo_tags_only_the_adr() -> None:
    from app.providers.yahoo import company_short_name

    assert company_short_name("HDFC Bank Limited") == "HDFC Bank"
    assert company_short_name("Infosys Limited") == "Infosys"
    assert company_short_name("Apple Inc.") == "Apple"
    assert company_short_name("XY Ltd") is None  # too short to match safely

    def search(query, max_results, news_count):
        news = [{"uuid": "h", "title": "HDFC Bank shares climb on loan growth", "publisher": "Wire",
                 "relatedTickers": ["HDB"]},
                {"uuid": "o", "title": "Indian banks mixed", "publisher": "Wire", "relatedTickers": ["HDB"]}]
        return type("S", (), {"news": news if query != "HDFCBANK.NS" else []})()

    class Ticker:
        info = {"longName": "HDFC Bank Limited"}

        def get_news(self, count):
            return []

    provider = YahooFinanceProvider(ticker_factory=lambda s: Ticker(), search_factory=search, sleeper=lambda _: None)
    feed = asyncio.run(provider.get_news("HDFCBANK.NS", 5))
    assert [i.title for i in feed.items] == ["HDFC Bank shares climb on loan growth"]
    assert "HDFCBANK.NS" not in feed.items[0].related_symbols  # stays labelled untagged


@pytest.mark.parametrize("symbols,expected", [
    (["TCS.NS"], "^NSEI"),
    (["RELIANCE.NS", "INFY.BO"], "^NSEI"),
    (["TCS.NS", "AAPL"], "SPY"),      # mixed markets keep the configured default
    (["AAPL"], "SPY"),
    ([], "SPY"),
])
def test_default_benchmark_follows_the_local_market(symbols, expected) -> None:
    from app.services.market_data import default_benchmark_for

    assert default_benchmark_for(symbols, "SPY") == expected
