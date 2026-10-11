"""Technical indicators on daily bars (pure, deterministic).

Conventions follow common charting platforms (TradingView, Kite):

* Indicators use the traded close (split-adjusted, not dividend-adjusted).
* ``None`` marks positions with insufficient history — never zero.
* SMA: arithmetic mean of the last *n* closes.
* EMA: ``alpha = 2 / (n + 1)``, seeded with the SMA of the first *n* closes.
* RSI: Wilder's smoothing (``alpha = 1 / n``), seeded with simple averages of
  the first *n* gains/losses; 100 when there are no losses.
* MACD: EMA(12) − EMA(26); signal = EMA(9) of MACD; histogram = MACD − signal.
* Bollinger Bands: SMA(20) ± 2 population standard deviations.
* ATR: Wilder-smoothed true range (needs high/low; ``None`` without them).
"""

import math
from collections.abc import Sequence

Series = list[float | None]


def sma(values: Sequence[float], n: int) -> Series:
    _check_window(n)
    out: Series = [None] * len(values)
    running = 0.0
    for i, value in enumerate(values):
        running += value
        if i >= n:
            running -= values[i - n]
        if i >= n - 1:
            out[i] = running / n
    return out


def ema(values: Sequence[float], n: int) -> Series:
    _check_window(n)
    out: Series = [None] * len(values)
    if len(values) < n:
        return out
    alpha = 2.0 / (n + 1)
    current = sum(values[:n]) / n
    out[n - 1] = current
    for i in range(n, len(values)):
        current = alpha * values[i] + (1 - alpha) * current
        out[i] = current
    return out


def _ema_of_optional(values: Series, n: int) -> Series:
    """EMA over a series that starts with ``None`` padding."""
    start = next((i for i, v in enumerate(values) if v is not None), None)
    out: Series = [None] * len(values)
    if start is None:
        return out
    tail = ema([v for v in values[start:] if v is not None], n)
    out[start:] = tail
    return out


def rsi(values: Sequence[float], n: int = 14) -> Series:
    _check_window(n)
    out: Series = [None] * len(values)
    if len(values) <= n:
        return out
    gains = [max(values[i] - values[i - 1], 0.0) for i in range(1, len(values))]
    losses = [max(values[i - 1] - values[i], 0.0) for i in range(1, len(values))]
    avg_gain = sum(gains[:n]) / n
    avg_loss = sum(losses[:n]) / n
    out[n] = _rsi_value(avg_gain, avg_loss)
    for i in range(n, len(gains)):
        avg_gain = (avg_gain * (n - 1) + gains[i]) / n
        avg_loss = (avg_loss * (n - 1) + losses[i]) / n
        out[i + 1] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def macd(values: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[Series, Series, Series]:
    fast_ema, slow_ema = ema(values, fast), ema(values, slow)
    line: Series = [
        f - s if f is not None and s is not None else None for f, s in zip(fast_ema, slow_ema)
    ]
    signal_line = _ema_of_optional(line, signal)
    histogram: Series = [
        m - s if m is not None and s is not None else None for m, s in zip(line, signal_line)
    ]
    return line, signal_line, histogram


def bollinger(values: Sequence[float], n: int = 20, k: float = 2.0) -> tuple[Series, Series, Series]:
    middle = sma(values, n)
    upper: Series = [None] * len(values)
    lower: Series = [None] * len(values)
    for i, mid in enumerate(middle):
        if mid is None:
            continue
        window = values[i - n + 1 : i + 1]
        sd = math.sqrt(sum((v - mid) ** 2 for v in window) / n)
        upper[i], lower[i] = mid + k * sd, mid - k * sd
    return upper, middle, lower


def atr(
    highs: Sequence[float | None], lows: Sequence[float | None], closes: Sequence[float], n: int = 14
) -> Series:
    _check_window(n)
    out: Series = [None] * len(closes)
    true_ranges: list[float] = []
    for i in range(1, len(closes)):
        high, low = highs[i], lows[i]
        if high is None or low is None:
            return out
        prev = closes[i - 1]
        true_ranges.append(max(high - low, abs(high - prev), abs(low - prev)))
    if len(true_ranges) < n:
        return out
    current = sum(true_ranges[:n]) / n
    out[n] = current
    for i in range(n, len(true_ranges)):
        current = (current * (n - 1) + true_ranges[i]) / n
        out[i + 1] = current
    return out


def crossovers(fast: Series, slow: Series) -> list[tuple[int, str]]:
    """Indices where ``fast`` crosses ``slow``: ("up" | "down")."""
    events: list[tuple[int, str]] = []
    for i in range(1, len(fast)):
        a0, b0, a1, b1 = fast[i - 1], slow[i - 1], fast[i], slow[i]
        if None in (a0, b0, a1, b1):
            continue
        if a0 <= b0 and a1 > b1:
            events.append((i, "up"))
        elif a0 >= b0 and a1 < b1:
            events.append((i, "down"))
    return events


def _check_window(n: int) -> None:
    if n < 1:
        raise ValueError("window must be at least 1")
