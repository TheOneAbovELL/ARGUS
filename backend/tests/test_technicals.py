"""Technical indicators: known answers, warm-up handling, and the API."""

import pytest
from fastapi.testclient import TestClient

from app.quant import technicals as ta


def test_sma_known_answer_and_warmup() -> None:
    assert ta.sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]


def test_ema_seeded_with_sma_then_recursive() -> None:
    values = [10.0, 11.0, 12.0, 13.0, 14.0]
    out = ta.ema(values, 3)
    alpha = 2 / 4
    seed = (10 + 11 + 12) / 3
    e3 = alpha * 13 + (1 - alpha) * seed
    e4 = alpha * 14 + (1 - alpha) * e3
    assert out[:2] == [None, None]
    assert out[2:] == pytest.approx([seed, e3, e4])


def test_rsi_wilder_known_answer() -> None:
    closes = [44.0, 44.5, 44.0, 45.0, 46.0, 45.5]
    n = 3
    gains = [0.5, 0.0, 1.0, 1.0, 0.0]
    losses = [0.0, 0.5, 0.0, 0.0, 0.5]
    ag, al = sum(gains[:n]) / n, sum(losses[:n]) / n
    expected = [100 - 100 / (1 + ag / al)]
    for gain, loss in zip(gains[n:], losses[n:]):
        ag, al = (ag * (n - 1) + gain) / n, (al * (n - 1) + loss) / n
        expected.append(100 - 100 / (1 + ag / al))
    out = ta.rsi(closes, n)
    assert out[:n] == [None] * n
    assert out[n:] == pytest.approx(expected)


def test_rsi_bounds_and_edge_cases() -> None:
    assert ta.rsi([1, 2, 3, 4, 5], 3)[-1] == 100.0  # no losses
    assert ta.rsi([5, 5, 5, 5, 5], 3)[-1] == 50.0  # no movement
    assert all(v is None or 0 <= v <= 100 for v in ta.rsi([3, 1, 4, 1, 5, 9, 2, 6, 5, 3], 3))


def test_macd_is_fast_minus_slow_and_signal_is_ema_of_macd() -> None:
    closes = [100 + i + (i % 3) for i in range(60)]
    line, signal, hist = ta.macd(closes, 12, 26, 9)
    fast, slow = ta.ema(closes, 12), ta.ema(closes, 26)
    assert line[25] == pytest.approx(fast[25] - slow[25])
    assert line[24] is None and signal[25 + 7] is None and signal[25 + 8] is not None
    assert hist[40] == pytest.approx(line[40] - signal[40])


def test_bollinger_uses_population_stdev() -> None:
    upper, middle, lower = ta.bollinger([1, 2, 3, 4], 4, 2)
    sd = (sum((v - 2.5) ** 2 for v in [1, 2, 3, 4]) / 4) ** 0.5
    assert middle[-1] == 2.5 and upper[-1] == pytest.approx(2.5 + 2 * sd) and lower[-1] == pytest.approx(2.5 - 2 * sd)


def test_atr_includes_gaps_and_needs_highs_lows() -> None:
    highs, lows, closes = [11, 12, 15, 14], [9, 10, 12, 12], [10, 11, 14, 13]
    out = ta.atr(highs, lows, closes, 2)
    tr = [max(12 - 10, abs(12 - 10), abs(10 - 10)), max(15 - 12, abs(15 - 11), abs(12 - 11)),
          max(14 - 12, abs(14 - 14), abs(12 - 14))]
    first = (tr[0] + tr[1]) / 2
    assert out[2] == pytest.approx(first)
    assert out[3] == pytest.approx((first * 1 + tr[2]) / 2)
    assert ta.atr([None] * 4, [None] * 4, closes, 2) == [None] * 4


def test_crossovers_detects_both_directions() -> None:
    fast = [1, 2, 3, 2, 1]
    slow = [2, 2, 2, 2, 2]
    assert ta.crossovers(fast, slow) == [(2, "up"), (4, "down")]


def test_technicals_endpoint_returns_aligned_series_and_explained_signals(client: TestClient) -> None:
    body = client.get("/api/market/NVDA/technicals", params={"period": "1y"}).json()
    n = len(body["dates"])
    assert n > 200
    for key in ("sma20", "sma50", "sma200", "ema20", "rsi14", "macd", "macd_signal", "macd_hist", "bb_upper", "bb_lower"):
        assert len(body["indicators"][key]) == n, key
    # warm-up history makes the 200-day average valid from the first visible bar
    assert body["indicators"]["sma200"][0] is not None
    keys = {s["key"] for s in body["signals"]}
    assert {"vs_sma50", "vs_sma200", "ma_cross", "rsi14", "macd", "bollinger", "range_52w"} <= keys
    assert all(s["reading"] and s["method"] for s in body["signals"])
    assert body["provenance"]["mode"] == "fixture"
    assert "not forecasts or recommendations" in body["conventions"]
    assert body["default_benchmark"] == "SPY"


def test_technicals_unknown_symbol_is_404(client: TestClient) -> None:
    assert client.get("/api/market/NOPE/technicals").status_code == 404
