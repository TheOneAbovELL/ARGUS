"""Chart data with technical indicators and an explained signal summary.

Indicators are computed on extra warm-up history before the requested window
(so a 200-day average is valid from the first visible bar), then trimmed to
the window. The summary states *conventional readings* of each indicator
(e.g. "RSI above 70 is conventionally read as overbought"); it is descriptive,
never a buy/sell recommendation.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.core.errors import InsufficientDataError
from app.providers.models import PriceHistory, Provenance
from app.quant import technicals as ta
from app.services.market_data import AnalysisWindow, MarketDataService

WARMUP_DAYS = 420  # > 200 trading days of lookback for SMA(200)


@dataclass(frozen=True)
class Signal:
    key: str
    label: str
    value: str
    tone: str  # positive | negative | neutral
    reading: str  # what the number means for this asset, in plain words
    method: str  # how it is computed / the convention behind the reading


@dataclass(frozen=True)
class TechnicalChart:
    symbol: str
    currency: str | None
    window: AnalysisWindow
    dates: list[date]
    open: list[float | None]
    high: list[float | None]
    low: list[float | None]
    close: list[float]
    volume: list[int | None]
    indicators: dict[str, list[float | None]]
    signals: list[Signal]
    high_52w: float | None
    low_52w: float | None
    last_close: float
    as_of: date
    provenance: Provenance
    quality_notes: list[str] = field(default_factory=list)


def _pct(a: float, b: float) -> float:
    return (a / b - 1.0) * 100.0


def build_chart(history: PriceHistory, window: AnalysisWindow) -> TechnicalChart:
    bars = history.bars
    closes = [b.close for b in bars]
    indicators_full = {
        "sma20": ta.sma(closes, 20),
        "sma50": ta.sma(closes, 50),
        "sma200": ta.sma(closes, 200),
        "ema20": ta.ema(closes, 20),
        "rsi14": ta.rsi(closes, 14),
        "atr14": ta.atr([b.high for b in bars], [b.low for b in bars], closes, 14),
    }
    upper, middle, lower = ta.bollinger(closes, 20, 2.0)
    indicators_full.update(bb_upper=upper, bb_middle=middle, bb_lower=lower)
    line, signal, hist = ta.macd(closes)
    indicators_full.update(macd=line, macd_signal=signal, macd_hist=hist)
    volumes = [b.volume for b in bars]
    vol_values = [float(v) if v is not None else 0.0 for v in volumes]
    indicators_full["volume_sma20"] = ta.sma(vol_values, 20) if all(v is not None for v in volumes) else [None] * len(bars)

    start = next((i for i, b in enumerate(bars) if b.date >= window.start), None)
    if start is None or len(bars) - start < 2:
        raise InsufficientDataError(
            f"'{history.symbol}' has fewer than two price observations in the selected window."
        )
    view = slice(start, len(bars))
    last = len(bars) - 1
    year_ago = bars[last].date - timedelta(days=365)
    year_bars = [b for b in bars if b.date > year_ago]
    high_52w = max((b.high or b.close) for b in year_bars) if year_bars else None
    low_52w = min((b.low or b.close) for b in year_bars) if year_bars else None

    return TechnicalChart(
        symbol=history.symbol,
        currency=history.currency,
        window=window,
        dates=[b.date for b in bars[view]],
        open=[b.open for b in bars[view]],
        high=[b.high for b in bars[view]],
        low=[b.low for b in bars[view]],
        close=closes[view],
        volume=volumes[view],
        indicators={k: v[view] for k, v in indicators_full.items()},
        signals=_signals(bars, closes, indicators_full, start, high_52w, low_52w, history.currency),
        high_52w=high_52w,
        low_52w=low_52w,
        last_close=closes[last],
        as_of=bars[last].date,
        provenance=history.provenance,
        quality_notes=list(history.quality_notes),
    )


def _signals(bars, closes, ind, start, high_52w, low_52w, currency) -> list[Signal]:
    i = len(closes) - 1
    price = closes[i]
    ccy = f" {currency}" if currency else ""
    out: list[Signal] = []

    for n in (50, 200):
        avg = ind[f"sma{n}"][i]
        if avg is None:
            continue
        diff = _pct(price, avg)
        above = diff >= 0
        out.append(Signal(
            key=f"vs_sma{n}",
            label=f"Price vs {n}-day average",
            value=f"{diff:+.1f}%",
            tone="positive" if above else "negative",
            reading=(
                f"The last close ({price:,.2f}{ccy}) is {abs(diff):.1f}% {'above' if above else 'below'} its "
                f"{n}-day average ({avg:,.2f}{ccy}). "
                + ("A price above a long average is conventionally read as an up-trend."
                   if above else "A price below a long average is conventionally read as a down-trend.")
            ),
            method=f"Simple moving average of the last {n} daily closes.",
        ))

    sma50, sma200 = ind["sma50"], ind["sma200"]
    if sma50[i] is not None and sma200[i] is not None:
        crosses = [(j, d) for j, d in ta.crossovers(sma50, sma200) if j >= start]
        golden = sma50[i] > sma200[i]
        last_cross = (
            f" The most recent cross in this window was a {'golden' if crosses[-1][1] == 'up' else 'death'} "
            f"cross on {bars[crosses[-1][0]].date.isoformat()}."
            if crosses else " There was no cross inside the selected window."
        )
        out.append(Signal(
            key="ma_cross",
            label="50-day vs 200-day average",
            value="50 > 200" if golden else "50 < 200",
            tone="positive" if golden else "negative",
            reading=(
                ("The 50-day average is above the 200-day average (a 'golden cross' regime)."
                 if golden else "The 50-day average is below the 200-day average (a 'death cross' regime).")
                + last_cross
            ),
            method="Compares the 50- and 200-day simple moving averages; crossings mark regime changes.",
        ))

    r = ind["rsi14"][i]
    if r is not None:
        zone = "overbought" if r >= 70 else "oversold" if r <= 30 else "neutral"
        out.append(Signal(
            key="rsi14",
            label="RSI (14)",
            value=f"{r:.1f}",
            tone="negative" if zone == "overbought" else "positive" if zone == "oversold" else "neutral",
            reading=(
                f"RSI is {r:.1f}. "
                + {"overbought": "Readings of 70 or more are conventionally called overbought: recent gains have been unusually strong relative to losses.",
                   "oversold": "Readings of 30 or less are conventionally called oversold: recent losses have been unusually strong relative to gains.",
                   "neutral": "Between 30 and 70 is the conventional neutral range."}[zone]
            ),
            method="Wilder's Relative Strength Index over 14 days: 100 − 100 / (1 + avg gain / avg loss).",
        ))

    m, s = ind["macd"][i], ind["macd_signal"][i]
    if m is not None and s is not None:
        crosses = [(j, d) for j, d in ta.crossovers(ind["macd"], ind["macd_signal"]) if j >= start]
        above = m > s
        recent = (
            f" It last crossed {'above' if crosses[-1][1] == 'up' else 'below'} the signal line on "
            f"{bars[crosses[-1][0]].date.isoformat()}." if crosses else ""
        )
        out.append(Signal(
            key="macd",
            label="MACD (12, 26, 9)",
            value=f"{m - s:+.2f}",
            tone="positive" if above else "negative",
            reading=(
                f"MACD ({m:.2f}) is {'above' if above else 'below'} its signal line ({s:.2f}), "
                f"i.e. short-term momentum is {'improving' if above else 'weakening'} relative to the longer trend."
                + recent
            ),
            method="EMA(12) − EMA(26) of closes; the signal line is the 9-day EMA of MACD.",
        ))

    up, lo = ind["bb_upper"][i], ind["bb_lower"][i]
    if up is not None and lo is not None and up > lo:
        pct_b = (price - lo) / (up - lo)
        out.append(Signal(
            key="bollinger",
            label="Bollinger %B (20, 2)",
            value=f"{pct_b:.2f}",
            tone="neutral",
            reading=(
                f"The close sits at {pct_b * 100:.0f}% of the way from the lower band ({lo:,.2f}) to the upper band "
                f"({up:,.2f}). Above 100% means it closed outside the upper band; below 0% outside the lower band."
            ),
            method="Bands are the 20-day average ± 2 standard deviations of closes.",
        ))

    a = ind["atr14"][i]
    if a is not None:
        atr_pct = a / price * 100
        out.append(Signal(
            key="atr14",
            label="Average true range (14)",
            value=f"{atr_pct:.2f}%",
            tone="neutral",
            reading=f"A typical day's range has been about {a:,.2f}{ccy} ({atr_pct:.2f}% of price) over the last 14 days.",
            method="Wilder-smoothed average of the daily true range (high − low, including gaps).",
        ))

    if high_52w is not None and low_52w is not None and high_52w > low_52w:
        position = (price - low_52w) / (high_52w - low_52w)
        out.append(Signal(
            key="range_52w",
            label="52-week range position",
            value=f"{position * 100:.0f}%",
            tone="neutral",
            reading=(
                f"The close is {abs(_pct(price, high_52w)):.1f}% below the 52-week high ({high_52w:,.2f}) and "
                f"{_pct(price, low_52w):.1f}% above the 52-week low ({low_52w:,.2f})."
            ),
            method="Uses daily highs and lows of the last 365 calendar days.",
        ))

    vol_avg = ind["volume_sma20"][i]
    last_vol = bars[i].volume
    if vol_avg and last_vol is not None:
        ratio = last_vol / vol_avg
        out.append(Signal(
            key="volume",
            label="Volume vs 20-day average",
            value=f"{ratio:.2f}×",
            tone="neutral",
            reading=(
                f"The last session traded {last_vol:,} shares, {ratio:.2f}× the 20-day average. "
                "Unusually high volume shows more participation behind the day's move."
            ),
            method="Last session volume divided by the 20-day simple average volume.",
        ))
    return out


class TechnicalsService:
    def __init__(self, market: MarketDataService) -> None:
        self._market = market

    async def chart(self, symbol: str, window: AnalysisWindow) -> TechnicalChart:
        extended = AnalysisWindow(
            start=max(date(1970, 1, 1), window.start - timedelta(days=WARMUP_DAYS)),
            end=window.end,
            label=window.label,
        )
        history = await self._market.history(symbol, extended)
        return build_chart(history, window)
