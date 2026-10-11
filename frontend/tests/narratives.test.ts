import { describe, expect, it } from 'vitest';
import { betaReading, drawdownReading, returnsReading, tailReading, volatilityReading } from '@/lib/narratives';
import type { AssetAnalysis } from '@/lib/types';

function analysis(overrides: Partial<AssetAnalysis['performance']> = {}, relative: Partial<NonNullable<AssetAnalysis['relative']>> | null = {}): AssetAnalysis {
  return {
    symbol: 'RELIANCE.NS',
    benchmark: '^NSEI',
    currency: 'INR',
    benchmark_currency: 'INR',
    window: { start: '2025-10-10', end: '2026-10-09', label: '1y' },
    periods_per_year: 252,
    risk_free_rate: 0,
    performance: {
      observations: 245,
      total_return: -0.2533,
      annualized_return: -0.2541,
      annualized_volatility: 0.2872,
      sharpe_ratio: -0.9,
      sortino_ratio: -1.2,
      max_drawdown: -0.3846,
      max_drawdown_peak: '2025-12-02',
      max_drawdown_trough: '2026-10-07',
      max_drawdown_recovery: null,
      longest_drawdown_days: 210,
      current_drawdown: -0.36,
      var_95: -0.0281,
      cvar_95: -0.039,
      best_period: 0.045,
      worst_period: -0.061,
      positive_periods_ratio: 0.46,
      ...overrides,
    },
    relative:
      relative === null
        ? null
        : {
            observations: 240,
            beta: 0.78,
            alpha: -0.2,
            correlation: 0.37,
            r_squared: 0.14,
            tracking_error: 0.25,
            information_ratio: -0.8,
            benchmark_total_return: 0.05,
            benchmark_annualized_return: 0.05,
            excess_annualized_return: -0.3041,
            ...relative,
          },
    series: {
      dates: ['2025-10-10', '2026-10-09'],
      close: [1500, 1170],
      adj_close: [1500, 1170],
      drawdown: [0, -0.36],
      rolling_volatility: [null, 0.31],
      daily_returns: [-0.22],
    },
    comparison: { dates: ['2025-10-10', '2026-10-09'], asset_cumulative: [0, -0.25], benchmark_cumulative: [0, 0.05], rolling_beta: [null, 0.9] },
    warnings: [],
    provenance: {},
  } as AssetAnalysis;
}

describe('narratives restate engine numbers in plain language', () => {
  it('returns: direction, magnitude and benchmark comparison', () => {
    const text = returnsReading(analysis());
    expect(text).toContain('RELIANCE.NS lost 25.3% in total');
    expect(text).toContain('^NSEI gained 5.0%');
    expect(text).toContain('underperformed by 30.4% a year');
  });

  it('drawdown: peak, trough, recovery status and duration', () => {
    const text = drawdownReading(analysis());
    expect(text).toContain('worst decline was 38.5%');
    expect(text).toContain('Dec 2, 2025');
    expect(text).toContain('has not recovered');
    expect(text).toContain('210 trading days');
    expect(drawdownReading(analysis({ max_drawdown: 0 }))).toContain('never closed below a previous high');
  });

  it('volatility compares recent and full-window values', () => {
    expect(volatilityReading(analysis())).toContain('Recent (63-day) volatility is 31.0% a year, higher than the 28.7%');
  });

  it('beta explains sensitivity and handles missing relative data', () => {
    expect(betaReading(analysis())).toContain('moved less than ^NSEI');
    expect(betaReading(analysis({}, null))).toBeNull();
  });

  it('tail risk never prints undefined values', () => {
    const text = tailReading(analysis({ var_95: null, cvar_95: null }));
    expect(text).not.toMatch(/undefined|NaN|null/);
    expect(text).toContain('46% of days closed higher');
  });
});

describe('portfolio narratives', () => {
  const base = {
    benchmark: 'SPY',
    start: '2023-10-11',
    end: '2026-10-09',
    periods_per_year: 252,
    assets: [
      { symbol: 'SPY', weight: 0.5, risk_contribution: 0.8 },
      { symbol: 'TLT', weight: 0.5, risk_contribution: -0.05 },
    ],
    correlation_symbols: ['SPY', 'QQQ', 'TLT'],
    correlation: [
      [1, 0.92, -0.2],
      [0.92, 1, -0.1],
      [-0.2, -0.1, 1],
    ],
    diversification_ratio: 1.25,
  } as unknown as import('@/lib/types').PortfolioAnalysis;

  it('risk allocation names the dominant holding and hedges', async () => {
    const { riskAllocationReading } = await import('@/lib/narratives');
    const text = riskAllocationReading(base)!;
    expect(text).toContain('SPY is 50% of the capital but 80% of the portfolio');
    expect(text).toContain('drives risk more than its weight');
    expect(text).toContain('TLT had a negative risk contribution');
  });

  it('correlation picks the extreme pairs and explains the diversification ratio', async () => {
    const { correlationReading } = await import('@/lib/narratives');
    const text = correlationReading(base)!;
    expect(text).toContain('SPY and QQQ (0.92)');
    expect(text).toContain('SPY and TLT (-0.20)');
    expect(text).toContain('20% lower');
  });
});
