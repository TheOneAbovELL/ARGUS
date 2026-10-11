"""Portfolio engine: model correctness and mathematical invariants."""

from datetime import date, datetime, timedelta

import numpy as np
import pytest

from app.portfolio.engine import (
    STRESS_EPISODES,
    PortfolioPosition,
    PortfolioValidationError,
    RebalancingModel,
    analyze_portfolio,
    portfolio_nav,
    stress_test,
)
from app.providers.models import DataMode, PriceBar, PriceHistory, Provenance
from app.quant.metrics import QuantDataError

PROVENANCE = Provenance("test", DataMode.FIXTURE, retrieved_at=datetime(2026, 1, 1))
START = date(2025, 1, 6)  # a Monday

PATHS = {
    "NVDA": [100.0, 104.0, 102.0, 108.0, 112.0, 109.0, 115.0],
    "MSFT": [100.0, 101.0, 103.0, 102.0, 105.0, 106.0, 104.0],
    "TLT": [100.0, 99.0, 100.5, 99.5, 98.0, 99.0, 100.0],
    "SPY": [100.0, 102.0, 101.0, 104.0, 106.0, 105.0, 107.0],
}


def history(symbol: str, prices: list[float], start: date = START, currency: str = "USD") -> PriceHistory:
    days, current = [], start
    while len(days) < len(prices):
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    bars = tuple(PriceBar(d, p, p, p, p, p) for d, p in zip(days, prices))
    return PriceHistory(symbol, currency, bars, PROVENANCE)


HISTORIES = {s: history(s, p) for s, p in PATHS.items()}
HOLDINGS = [PortfolioPosition("NVDA", 0.5), PortfolioPosition("MSFT", 0.3), PortfolioPosition("TLT", 0.2)]


def run(model: RebalancingModel, holdings=HOLDINGS):
    return analyze_portfolio(holdings, HISTORIES, HISTORIES["SPY"], "SPY", model, 0.0)


def test_daily_rebalanced_nav_matches_hand_calculation() -> None:
    result = run(RebalancingModel.DAILY_REBALANCED)
    nav = [1.0]
    for t in range(1, 7):
        r = sum(h.weight * (PATHS[h.ticker][t] / PATHS[h.ticker][t - 1] - 1) for h in HOLDINGS)
        nav.append(nav[-1] * (1 + r))
    assert list(result.series.cumulative_return) == pytest.approx([v - 1 for v in nav])


def test_buy_and_hold_nav_is_weighted_price_relatives_not_averaged_returns() -> None:
    result = run(RebalancingModel.BUY_AND_HOLD)
    expected = [sum(h.weight * PATHS[h.ticker][t] / PATHS[h.ticker][0] for h in HOLDINGS) - 1 for t in range(7)]
    assert list(result.series.cumulative_return) == pytest.approx(expected)
    # ending weights drift with relative performance and still sum to 1
    endings = {a.symbol: a.ending_weight for a in result.assets}
    assert sum(endings.values()) == pytest.approx(1.0)
    assert endings["NVDA"] > 0.5  # NVDA outperformed, so its weight grew


def test_models_differ_when_prices_diverge() -> None:
    rebalanced = run(RebalancingModel.DAILY_REBALANCED).performance.total_return
    held = run(RebalancingModel.BUY_AND_HOLD).performance.total_return
    assert rebalanced != pytest.approx(held, abs=1e-9)


def test_risk_contributions_sum_to_one_and_return_contributions_sum_to_total() -> None:
    result = run(RebalancingModel.BUY_AND_HOLD)
    assert sum(a.risk_contribution for a in result.assets) == pytest.approx(1.0)
    assert sum(a.return_contribution for a in result.assets) == pytest.approx(result.performance.total_return)


def test_risk_contribution_matches_independent_covariance_formula() -> None:
    result = run(RebalancingModel.DAILY_REBALANCED)
    prices = np.array([PATHS[h.ticker] for h in HOLDINGS]).T
    returns = prices[1:] / prices[:-1] - 1
    cov = np.cov(returns, rowvar=False) * 252
    w = np.array([h.weight for h in HOLDINGS])
    sigma = np.sqrt(w @ cov @ w)
    expected = w * (cov @ w) / sigma**2
    assert [a.risk_contribution for a in result.assets] == pytest.approx(list(expected))
    vols = np.sqrt(np.diag(cov))
    assert result.diversification_ratio == pytest.approx(float(w @ vols / sigma))


def test_correlation_matrix_is_symmetric_bounded_with_unit_diagonal() -> None:
    matrix = np.array(run(RebalancingModel.DAILY_REBALANCED).correlation, dtype=float)
    assert np.allclose(matrix, matrix.T)
    assert np.allclose(np.diag(matrix), 1.0)
    assert np.all(matrix <= 1.0) and np.all(matrix >= -1.0)


def test_single_asset_portfolio_equals_the_asset() -> None:
    result = run(RebalancingModel.DAILY_REBALANCED, [PortfolioPosition("NVDA", 1.0)])
    assert result.performance.total_return == pytest.approx(PATHS["NVDA"][-1] / PATHS["NVDA"][0] - 1)
    assert result.assets[0].risk_contribution == pytest.approx(1.0)


def test_portfolio_nav_buy_and_hold_ending_weights() -> None:
    prices = np.array([[10.0, 20.0], [20.0, 20.0]])
    nav, ending = portfolio_nav(prices, np.array([0.5, 0.5]), RebalancingModel.BUY_AND_HOLD)
    assert list(nav) == pytest.approx([1.0, 1.5])
    assert list(ending) == pytest.approx([2 / 3, 1 / 3])


@pytest.mark.parametrize(
    "holdings",
    [
        [],
        [PortfolioPosition("NVDA", 0.8)],
        [PortfolioPosition("NVDA", 0.5), PortfolioPosition("NVDA", 0.5)],
        [PortfolioPosition("NVDA", 1.1), PortfolioPosition("MSFT", -0.1)],
        [PortfolioPosition("NVDA", float("nan")), PortfolioPosition("MSFT", 1.0)],
    ],
)
def test_invalid_allocations_are_rejected(holdings) -> None:
    with pytest.raises(PortfolioValidationError):
        run(RebalancingModel.DAILY_REBALANCED, holdings)


def test_missing_history_is_an_error_not_a_silent_reweight() -> None:
    with pytest.raises(QuantDataError):
        analyze_portfolio(
            [PortfolioPosition("NVDA", 0.5), PortfolioPosition("XXX", 0.5)],
            HISTORIES, HISTORIES["SPY"], "SPY", RebalancingModel.DAILY_REBALANCED, 0.0,
        )


def test_late_listing_truncates_window_with_warning() -> None:
    late = history("NEW", [50.0, 51.0, 52.0, 53.0], start=date(2025, 1, 9))
    histories = {**HISTORIES, "NEW": late}
    result = analyze_portfolio(
        [PortfolioPosition("NVDA", 0.5), PortfolioPosition("NEW", 0.5)],
        histories, HISTORIES["SPY"], "SPY", RebalancingModel.DAILY_REBALANCED, 0.0,
        requested_start=date(2024, 12, 1),
    )
    assert result.start == date(2025, 1, 9)
    assert any("NEW has no earlier history" in w for w in result.warnings)


def test_mixed_currencies_are_flagged() -> None:
    eur = history("SAP.DE", PATHS["MSFT"], currency="EUR")
    result = analyze_portfolio(
        [PortfolioPosition("NVDA", 0.5), PortfolioPosition("SAP.DE", 0.5)],
        {**HISTORIES, "SAP.DE": eur}, HISTORIES["SPY"], "SPY", RebalancingModel.DAILY_REBALANCED, 0.0,
    )
    assert any("multiple currencies" in w for w in result.warnings)


def test_stress_test_replays_episode_and_skips_missing_history() -> None:
    covid = next(e for e in STRESS_EPISODES if e.key == "covid")
    days = _business_days_between(covid.start, covid.end)
    a = history("AAA", [100.0, 90.0, 80.0] + [85.0] * (days - 3), start=covid.start)
    b = history("BBB", [100.0, 100.0, 110.0] + [105.0] * (days - 3), start=covid.start)
    results = {r.episode.key: r for r in stress_test(
        [PortfolioPosition("AAA", 0.5), PortfolioPosition("BBB", 0.5)], {"AAA": a, "BBB": b}, None
    )}
    covid_result = results["covid"]
    assert covid_result.computable
    assert covid_result.portfolio_return == pytest.approx(0.5 * 0.85 + 0.5 * 1.05 - 1)
    assert covid_result.portfolio_max_drawdown == pytest.approx(0.5 * 0.8 + 0.5 * 1.1 - 1)
    assert results["gfc"].computable is False
    assert set(results["gfc"].missing_symbols) == {"AAA", "BBB"}


def _business_days_between(start: date, end: date) -> int:
    return sum(1 for i in range((end - start).days + 1) if (start + timedelta(days=i)).weekday() < 5)


def test_stress_test_rejects_history_that_ends_before_the_episode_does() -> None:
    covid = next(e for e in STRESS_EPISODES if e.key == "covid")
    days = _business_days_between(covid.start, covid.end)
    full = history("AAA", [100.0 - i for i in range(days)], start=covid.start)
    truncated = history("BBB", [100.0, 99.0, 98.0, 97.0, 96.0, 95.0, 94.0], start=covid.start)
    result = {r.episode.key: r for r in stress_test(
        [PortfolioPosition("AAA", 0.5), PortfolioPosition("BBB", 0.5)], {"AAA": full, "BBB": truncated}, None
    )}["covid"]
    assert result.computable is False
    assert result.missing_symbols == ("BBB",)


def test_stress_benchmark_is_measured_over_the_portfolio_dates() -> None:
    covid = next(e for e in STRESS_EPISODES if e.key == "covid")
    days = _business_days_between(covid.start, covid.end)
    # The holding starts 3 business days late (inside the grace period).
    late_start = covid.start + timedelta(days=5)  # Wed 2020-02-19 + 5 = Mon 2020-02-24
    late_days = _business_days_between(late_start, covid.end)
    asset = history("AAA", [100.0] * late_days, start=late_start)
    bench_prices = [100.0 + i for i in range(days)]
    bench = history("SPY", bench_prices, start=covid.start)
    result = {r.episode.key: r for r in stress_test([PortfolioPosition("AAA", 1.0)], {"AAA": asset}, bench)}["covid"]
    assert result.computable
    offset = days - late_days
    assert result.benchmark_return == pytest.approx(bench_prices[-1] / bench_prices[offset] - 1)


def test_single_constant_asset_has_undefined_self_correlation() -> None:
    flat = history("CASH", [100.0] * 7)
    result = analyze_portfolio(
        [PortfolioPosition("CASH", 1.0)], {"CASH": flat}, HISTORIES["SPY"], "SPY", RebalancingModel.BUY_AND_HOLD, 0.0
    )
    assert result.correlation == ((None,),)


def test_extreme_short_window_cagr_overflow_is_undefined_not_a_crash() -> None:
    explosive = history("XXX", [1.0, 10.0, 100.0])
    calm = history("YYY", [1.0, 1.0, 1.01])
    bench = history("SPY", [100.0, 101.0, 102.0])
    result = analyze_portfolio(
        [PortfolioPosition("XXX", 0.5), PortfolioPosition("YYY", 0.5)],
        {"XXX": explosive, "YYY": calm}, bench, "SPY", RebalancingModel.BUY_AND_HOLD, 0.0,
    )
    xxx = next(a for a in result.assets if a.symbol == "XXX")
    assert xxx.annualized_return is None
    assert any("XXX: annualized return is undefined" in w for w in result.warnings)
