"""Known-answer and invariant tests for the extended quant library.

Expected values are computed independently by hand (or with plain numpy in
the test) rather than by calling the function under test.
"""

import math
import statistics
from datetime import date, timedelta

import numpy as np
import pytest

from app.quant.drawdown import drawdown_series, drawdown_stats
from app.quant.metrics import QuantDataError, performance_metrics, relative_metrics
from app.quant.relative import correlation, information_ratio, regression_stats, tracking_error
from app.quant.returns import (
    calendar_annualized_return,
    cumulative_returns,
    infer_periods_per_year,
    log_returns,
    total_return,
)
from app.quant.risk import downside_deviation, historical_cvar, historical_var, sortino_ratio
from app.quant.series import align_on_common_dates, rolling_beta, rolling_volatility


def business_days(n: int, start: date = date(2024, 1, 1)) -> list[date]:
    days, current = [], start
    while len(days) < n:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


# ── returns ───────────────────────────────────────────────────────────


def test_log_and_cumulative_returns_known_answers() -> None:
    prices = [100.0, 110.0, 99.0]
    assert log_returns(prices) == pytest.approx([math.log(1.1), math.log(0.9)])
    assert cumulative_returns(prices) == pytest.approx([0.0, 0.10, -0.01])
    assert total_return(prices) == pytest.approx(-0.01)


def test_calendar_cagr_doubles_over_one_julian_year() -> None:
    start = date(2020, 1, 1)
    end = start + timedelta(days=365)  # 365 / 365.25 years
    expected = 2.0 ** (365.25 / 365) - 1
    assert calendar_annualized_return(100, 200, start, end) == pytest.approx(expected)


def test_calendar_cagr_rejects_zero_elapsed_time() -> None:
    with pytest.raises(ValueError):
        calendar_annualized_return(100, 101, date(2020, 1, 1), date(2020, 1, 1))


def test_periods_per_year_detects_weekend_trading() -> None:
    weekdays = business_days(30)
    every_day = [date(2024, 1, 1) + timedelta(days=i) for i in range(30)]
    assert infer_periods_per_year(weekdays) == 252
    assert infer_periods_per_year(every_day) == 365


# ── drawdown ──────────────────────────────────────────────────────────


def test_drawdown_series_never_positive_and_matches_running_peak() -> None:
    prices = [100.0, 120.0, 90.0, 110.0, 130.0, 117.0]
    series = drawdown_series(prices)
    assert series == pytest.approx([0, 0, -0.25, 110 / 120 - 1, 0, -0.1])
    assert all(value <= 0 for value in series)


def test_drawdown_stats_reports_peak_trough_recovery_and_duration() -> None:
    prices = [100.0, 120.0, 90.0, 110.0, 130.0, 117.0]
    stats = drawdown_stats(prices)
    assert stats.max_drawdown == pytest.approx(-0.25)
    assert (stats.peak_index, stats.trough_index, stats.recovery_index) == (1, 2, 4)
    assert stats.longest_underwater_periods == 3  # peak at 1, regained at 4
    assert stats.current_drawdown == pytest.approx(-0.1)


def test_drawdown_stats_unrecovered_spell_runs_to_end() -> None:
    stats = drawdown_stats([100.0, 90.0, 95.0, 80.0])
    assert stats.recovery_index is None
    assert stats.longest_underwater_periods == 3


# ── downside risk ─────────────────────────────────────────────────────


def test_downside_deviation_counts_all_periods() -> None:
    returns = [0.02, -0.01, 0.03, -0.03]
    expected = math.sqrt((0.01**2 + 0.03**2) / 4)
    assert downside_deviation(returns) == pytest.approx(expected)


def test_sortino_known_answer() -> None:
    returns = [0.02, -0.01, 0.03, -0.03]
    expected = statistics.mean(returns) / math.sqrt((0.01**2 + 0.03**2) / 4) * math.sqrt(252)
    assert sortino_ratio(returns) == pytest.approx(expected)


def test_sortino_is_undefined_without_downside() -> None:
    with pytest.raises(ValueError):
        sortino_ratio([0.01, 0.02, 0.03])


def test_historical_var_and_cvar_known_answers() -> None:
    returns = [i / 100 for i in range(-10, 10)]  # -0.10 .. 0.09, 20 values
    expected_var = float(np.quantile(returns, 0.05))
    assert historical_var(returns) == pytest.approx(expected_var)
    tail = [r for r in returns if r <= expected_var]
    assert historical_cvar(returns) == pytest.approx(statistics.mean(tail))
    assert historical_cvar(returns) <= historical_var(returns)


def test_var_requires_enough_observations() -> None:
    with pytest.raises(ValueError):
        historical_var([0.01] * 10)


# ── relative statistics ───────────────────────────────────────────────


def test_regression_recovers_known_beta_and_alpha() -> None:
    bench = [0.01, -0.02, 0.015, 0.03, -0.01, 0.005]
    daily_alpha = 0.001
    asset = [daily_alpha + 1.5 * b for b in bench]
    stats = regression_stats(asset, bench, annual_risk_free_rate=0.0)
    assert stats.beta == pytest.approx(1.5)
    assert stats.alpha == pytest.approx(daily_alpha * 252)
    assert stats.correlation == pytest.approx(1.0)
    assert stats.r_squared == pytest.approx(1.0)


def test_correlation_bounds_and_constant_series() -> None:
    a = [0.01, -0.02, 0.03, 0.0]
    assert -1.0 <= correlation(a, [-x for x in a]) == pytest.approx(-1.0)
    with pytest.raises(ValueError):
        correlation(a, [0.01] * 4)


def test_tracking_error_and_information_ratio() -> None:
    bench = [0.01, -0.01, 0.02, 0.0]
    asset = [0.012, -0.009, 0.019, 0.004]
    active = [a - b for a, b in zip(asset, bench)]
    te = statistics.stdev(active) * math.sqrt(252)
    assert tracking_error(asset, bench) == pytest.approx(te)
    assert information_ratio(asset, bench) == pytest.approx(statistics.mean(active) * 252 / te)
    with pytest.raises(ValueError):
        information_ratio(bench, bench)


# ── rolling / alignment ───────────────────────────────────────────────


def test_rolling_volatility_pads_with_none_and_matches_numpy() -> None:
    returns = [0.01, -0.02, 0.03, 0.0, 0.01]
    result = rolling_volatility(returns, window=3)
    assert result[:2] == [None, None]
    assert result[2] == pytest.approx(np.std(returns[0:3], ddof=1) * math.sqrt(252))
    assert result[4] == pytest.approx(np.std(returns[2:5], ddof=1) * math.sqrt(252))


def test_rolling_beta_equals_constant_multiplier() -> None:
    bench = [0.01, -0.02, 0.03, 0.0, 0.01, -0.005]
    beta = rolling_beta([2 * b for b in bench], bench, window=4)
    assert beta[:3] == [None, None, None]
    assert all(value == pytest.approx(2.0) for value in beta[3:])


def test_alignment_is_an_inner_join_without_forward_fill() -> None:
    d = business_days(4)
    dates, aligned = align_on_common_dates(
        {"a": {d[0]: 1.0, d[1]: 2.0, d[3]: 4.0}, "b": {d[0]: 10.0, d[2]: 30.0, d[3]: 40.0}}
    )
    assert dates == [d[0], d[3]]
    assert aligned == {"a": [1.0, 4.0], "b": [10.0, 40.0]}


# ── aggregate metric sets ─────────────────────────────────────────────


def test_performance_metrics_reports_undefined_ratios_as_none_not_zero() -> None:
    days = business_days(5)
    flat_growth = [100.0 * (1.01**i) for i in range(5)]  # constant returns
    metrics, warnings = performance_metrics(days, flat_growth, 0.0, 252)
    assert metrics.annualized_volatility == pytest.approx(0.0, abs=1e-12)
    assert metrics.sharpe_ratio is None
    assert metrics.sortino_ratio is None
    assert metrics.var_95 is None
    assert any("sharpe_ratio" in w for w in warnings)
    assert any("unreliable" in w for w in warnings)  # short-history warning
    assert metrics.max_drawdown == 0.0


def test_performance_metrics_rejects_invalid_prices() -> None:
    days = business_days(3)
    with pytest.raises(QuantDataError):
        performance_metrics(days, [100.0, -1.0, 101.0], 0.0, 252)
    with pytest.raises(QuantDataError):
        performance_metrics(days[:2], [100.0, 101.0], 0.0, 252)


def test_relative_metrics_against_identical_benchmark() -> None:
    days = business_days(30)
    rng = np.random.default_rng(7)
    prices = list(100 * np.cumprod(1 + rng.normal(0, 0.01, 30)))
    metrics, _ = relative_metrics(days, prices, prices, 0.0, 252)
    assert metrics.beta == pytest.approx(1.0)
    assert metrics.correlation == pytest.approx(1.0)
    assert metrics.alpha == pytest.approx(0.0, abs=1e-12)
    assert metrics.tracking_error == pytest.approx(0.0, abs=1e-12)
    assert metrics.information_ratio is None  # undefined, not 0
    assert metrics.excess_annualized_return == pytest.approx(0.0, abs=1e-12)


def test_drawdown_peak_is_the_latest_high_before_the_trough() -> None:
    stats = drawdown_stats([100.0, 90.0, 100.0, 50.0, 60.0])
    assert stats.peak_index == 2
    assert stats.trough_index == 3
    assert stats.max_drawdown == pytest.approx(-0.5)


def test_periods_per_year_uses_density_not_saturday_sunday() -> None:
    # Sun-Thu exchange (e.g. Tadawul): ~5 sessions a week -> 252, not 365.
    sun_to_thu, day = [], date(2024, 1, 7)  # a Sunday
    while len(sun_to_thu) < 250:
        if day.weekday() in (6, 0, 1, 2, 3):
            sun_to_thu.append(day)
        day += timedelta(days=1)
    assert infer_periods_per_year(sun_to_thu) == 252
    every_day = [date(2024, 1, 1) + timedelta(days=i) for i in range(200)]
    assert infer_periods_per_year(every_day) == 365
    assert infer_periods_per_year([date(2024, 1, 1)]) == 252


def test_constant_asset_keeps_beta_and_alpha_but_not_correlation() -> None:
    bench = [0.01, -0.02, 0.015, 0.0, 0.005]
    stats = regression_stats([0.0] * 5, bench, annual_risk_free_rate=0.0, periods_per_year=252)
    assert stats.beta == pytest.approx(0.0)
    assert stats.alpha == pytest.approx(0.0)
    assert stats.correlation is None and stats.r_squared is None
