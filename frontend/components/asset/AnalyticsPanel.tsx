'use client';

import { useMemo, useState } from 'react';
import { Info } from 'lucide-react';
import { api } from '@/lib/api';
import { useAsync } from '@/lib/useAsync';
import { DASH, num, pct, PERIODS, shortDate, type Period } from '@/lib/format';
import { betaReading, drawdownReading, returnsReading, tailReading, volatilityReading } from '@/lib/narratives';
import type { AssetAnalysis } from '@/lib/types';
import TimeSeriesChart from '@/components/charts/TimeSeriesChart';
import DataBadge from '@/components/DataBadge';
import KeyFigure, { KeyFigures } from '@/components/KeyFigure';
import { AnalysisSection, ErrorNotice, LoadingBlock, Notes, SegmentedControl, StatList } from '@/components/ui';

const PERIOD_OPTIONS = PERIODS.filter((p) => p !== '1mo').map((p) => ({ value: p, label: p.toUpperCase() }));

const isNum = (v: number | null | undefined): v is number => typeof v === 'number' && Number.isFinite(v);
const tone = (v: number | null | undefined) => (!isNum(v) || v === 0 ? undefined : v > 0 ? 'text-up' : 'text-down');

function ReturnDistribution({ returns, varValue }: { returns: number[]; varValue: number | null }) {
  const bins = useMemo(() => {
    if (returns.length < 10) return null;
    const sorted = [...returns].sort((x, y) => x - y);
    // Clip the display range at the 0.5th/99.5th percentiles so one outlier
    // does not flatten the histogram; clipped days fall into the edge bins.
    const lo = sorted[Math.floor(sorted.length * 0.005)];
    const hi = sorted[Math.ceil(sorted.length * 0.995) - 1];
    const count = 51;
    const width = (hi - lo) / count || 1e-6;
    const counts = new Array(count).fill(0);
    for (const r of returns) counts[Math.min(count - 1, Math.max(0, Math.floor((r - lo) / width)))]++;
    return { counts, lo, hi: lo + count * width, width, max: Math.max(...counts) };
  }, [returns]);
  if (!bins) return <p className="text-[13px] text-ink-muted">Not enough returns for a distribution.</p>;
  const at = (v: number) => `${((v - bins.lo) / (bins.hi - bins.lo)) * 100}%`;
  const showZero = bins.lo < 0 && bins.hi > 0;
  const showVar = isNum(varValue) && varValue > bins.lo && varValue < bins.hi;
  return (
    <figure aria-label="Histogram of daily returns" className="select-none">
      <div className="relative h-44 border-b border-line">
        <div className="flex h-full items-end gap-px">
          {bins.counts.map((c, i) => {
            const center = bins.lo + (i + 0.5) * bins.width;
            const inTail = isNum(varValue) && center <= varValue;
            return (
              <div
                key={i}
                className={`flex-1 rounded-t-[1px] ${inTail ? 'bg-down' : center < 0 ? 'bg-down/35' : 'bg-up/45'}`}
                style={{ height: `${(c / bins.max) * 100}%` }}
                title={`${pct(bins.lo + i * bins.width, 2)} to ${pct(bins.lo + (i + 1) * bins.width, 2)}: ${c} day${c === 1 ? '' : 's'}`}
              />
            );
          })}
        </div>
        {showZero && <div className="pointer-events-none absolute inset-y-0 w-px bg-ink-faint/60" style={{ left: at(0) }} aria-hidden />}
        {showVar && (
          <div className="pointer-events-none absolute inset-y-0 border-l border-dashed border-down" style={{ left: at(varValue!) }} aria-hidden>
            <span className="num absolute -top-0.5 left-1 whitespace-nowrap text-2xs text-down">VaR 95% {pct(varValue, 1)}</span>
          </div>
        )}
      </div>
      <figcaption className="num relative mt-1 h-4 text-2xs text-ink-faint">
        <span className="absolute left-0">{pct(bins.lo, 1)}</span>
        {showZero && (
          <span className="absolute -translate-x-1/2" style={{ left: at(0) }}>
            0%
          </span>
        )}
        <span className="absolute right-0">{pct(bins.hi, 1)}</span>
      </figcaption>
      <p className="mt-1 text-2xs text-ink-faint">
        Bar height = number of days whose return fell in that bucket. Solid red bars are days at or below the 95% VaR line.
      </p>
    </figure>
  );
}

export default function AnalyticsPanel({ symbol }: { symbol: string }) {
  const [period, setPeriod] = useState<Period>('1y');
  // Empty = automatic: the backend picks the market's index (SPY, or ^NSEI for .NS/.BO listings).
  const [benchmarkInput, setBenchmarkInput] = useState('');
  const [benchmark, setBenchmark] = useState('');
  const [rateInput, setRateInput] = useState('0');
  const [rate, setRate] = useState(0);

  const { data, error, loading, reload } = useAsync<AssetAnalysis>(
    () => api.analyzeAsset({ symbol, period, benchmark: benchmark || undefined, risk_free_rate: rate }),
    [symbol, period, benchmark, rate],
  );

  const applySettings = (event: React.FormEvent) => {
    event.preventDefault();
    const parsed = Number(rateInput);
    setBenchmark(benchmarkInput.trim().toUpperCase());
    setRate(Number.isFinite(parsed) ? Math.max(-5, Math.min(25, parsed)) / 100 : 0);
  };

  const unit = data?.periods_per_year === 365 ? 'days' : 'trading days';

  return (
    <div className="space-y-8">
      <form onSubmit={applySettings} className="flex flex-wrap items-end gap-x-5 gap-y-3 border-b border-line pb-4">
        <div>
          <span className="label">Window</span>
          <SegmentedControl label="Analysis window" size="xs" options={PERIOD_OPTIONS} value={period} onChange={setPeriod} />
        </div>
        <div className="w-32">
          <label className="label" htmlFor="benchmark">
            Benchmark
          </label>
          <input
            id="benchmark"
            className="input num uppercase placeholder:normal-case"
            value={benchmarkInput}
            placeholder={data && !benchmark ? `Auto: ${data.benchmark}` : 'Auto'}
            title="Leave empty to use the market's index (SPY; ^NSEI for NSE/BSE listings)"
            onChange={(e) => setBenchmarkInput(e.target.value)}
          />
        </div>
        <div className="w-28">
          <label className="label" htmlFor="rf">
            Risk-free %
          </label>
          <input id="rf" className="input num" inputMode="decimal" value={rateInput} onChange={(e) => setRateInput(e.target.value)} />
        </div>
        <button type="submit" className="btn-ghost">
          Apply
        </button>
        {data && (
          <p className="ml-auto text-xs text-ink-faint">
            {shortDate(data.window.start)} – {shortDate(data.series.dates[data.series.dates.length - 1])} · {data.periods_per_year} periods/yr ·{' '}
            {data.currency ?? 'currency n/a'}
          </p>
        )}
      </form>

      {loading && !data && <LoadingBlock rows={8} label="Computing analytics" />}
      {error ? <ErrorNotice error={error} onRetry={reload} /> : null}

      {data && (
        <div className={`space-y-10 ${loading ? 'opacity-60 transition-opacity' : ''}`}>
          {data.warnings.length > 0 && <Notes title="Data and calculation notes" items={data.warnings} />}

          <section aria-label="Return & risk" className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="section-title">Return &amp; risk</h2>
              <div className="flex flex-wrap gap-3">
                {Object.entries(data.provenance).map(([sym, p]) => (
                  <span key={sym} className="inline-flex items-center gap-1 text-2xs text-ink-faint">
                    {sym} <DataBadge provenance={p} />
                  </span>
                ))}
              </div>
            </div>
            <KeyFigures>
              <KeyFigure metric="total_return" label="Total return" value={pct(data.performance.total_return)} toneClass={tone(data.performance.total_return)} sub={`${data.performance.observations} daily returns`} />
              <KeyFigure
                metric="annualized_return"
                label="Annualized return"
                value={pct(data.performance.annualized_return)}
                toneClass={tone(data.performance.annualized_return)}
                sub="compound annual growth"
              />
              <KeyFigure metric="annualized_volatility" label="Annualized volatility" value={pct(data.performance.annualized_volatility)} sub={`std. dev. of daily returns × √${data.periods_per_year}`} />
              <KeyFigure
                metric="sharpe_ratio"
                label="Sharpe ratio"
                value={num(data.performance.sharpe_ratio)}
                toneClass={tone(data.performance.sharpe_ratio)}
                sub={isNum(data.performance.sharpe_ratio) ? `risk-free ${pct(data.risk_free_rate, 2)}` : 'undefined for this window'}
              />
              <KeyFigure
                metric="max_drawdown"
                label="Max drawdown"
                value={pct(data.performance.max_drawdown)}
                toneClass={data.performance.max_drawdown < 0 ? 'text-down' : undefined}
                sub={`${shortDate(data.performance.max_drawdown_peak)} → ${shortDate(data.performance.max_drawdown_trough)}`}
              />
              <KeyFigure
                metric="var_95"
                label="1-day VaR 95%"
                value={pct(data.performance.var_95)}
                toneClass="text-down"
                sub={isNum(data.performance.var_95) ? 'historical, 1 in 20 days' : 'needs ≥ 20 returns'}
              />
            </KeyFigures>
          </section>

          {data.comparison && (
            <AnalysisSection
              title={`Cumulative return vs ${data.benchmark}`}
              what={
                <>
                  What one unit invested at the start of the window would have become, as a percentage gain or loss, for <strong>{data.symbol}</strong>{' '}
                  (blue) and <strong>{data.benchmark}</strong> (orange). Both lines start at 0% and use dividend-adjusted closes on the dates
                  both traded. The gap between them is the out- or under-performance.
                </>
              }
              reading={returnsReading(data)}
              aside={
                <StatList
                  rows={[
                    { label: `${data.symbol} total`, value: pct(data.performance.total_return), tone: tone(data.performance.total_return) },
                    { label: `${data.symbol} annualized`, value: pct(data.performance.annualized_return), tone: tone(data.performance.annualized_return) },
                    ...(data.relative
                      ? [
                          { label: `${data.benchmark} total`, value: pct(data.relative.benchmark_total_return), tone: tone(data.relative.benchmark_total_return) },
                          {
                            label: `${data.benchmark} annualized`,
                            value: pct(data.relative.benchmark_annualized_return),
                            tone: tone(data.relative.benchmark_annualized_return),
                          },
                          {
                            label: 'Excess (annualized)',
                            value: pct(data.relative.excess_annualized_return, 2, true),
                            tone: tone(data.relative.excess_annualized_return),
                            hint: 'Asset annualized return minus benchmark annualized return',
                          },
                        ]
                      : []),
                  ]}
                />
              }
            >
              <TimeSeriesChart
                ariaLabel="Cumulative return comparison"
                height={320}
                referenceLines={[{ value: 0, label: 'start' }]}
                series={[
                  { id: 'asset', label: data.symbol, type: 'line', color: 'accent', dates: data.comparison.dates, values: data.comparison.asset_cumulative, format: 'percent' },
                  { id: 'bench', label: data.benchmark, type: 'line', color: 'chart-1', dates: data.comparison.dates, values: data.comparison.benchmark_cumulative, format: 'percent', lineWidth: 1 },
                ]}
              />
            </AnalysisSection>
          )}

          <AnalysisSection
            title="Drawdown from running peak"
            what={
              <>
                How far the price sat below its highest close so far, on every day. 0% means the stock was at a new high; a deep, wide valley means
                a large loss that took a long time to recover. This is the pain an investor who bought at the top would have felt.
              </>
            }
            reading={drawdownReading(data)}
            aside={
              <StatList
                rows={[
                  { label: 'Max drawdown', value: pct(data.performance.max_drawdown), tone: data.performance.max_drawdown < 0 ? 'text-down' : undefined },
                  { label: 'Peak', value: shortDate(data.performance.max_drawdown_peak) },
                  { label: 'Trough', value: shortDate(data.performance.max_drawdown_trough) },
                  { label: 'Recovered', value: data.performance.max_drawdown_recovery ? shortDate(data.performance.max_drawdown_recovery) : 'Not yet' },
                  { label: 'Longest underwater', value: `${data.performance.longest_drawdown_days} ${unit}` },
                  { label: 'Current drawdown', value: pct(data.performance.current_drawdown), tone: data.performance.current_drawdown < 0 ? 'text-down' : undefined },
                ]}
              />
            }
          >
            <TimeSeriesChart
              ariaLabel="Drawdown"
              height={240}
              referenceLines={data.performance.max_drawdown < 0 ? [{ value: data.performance.max_drawdown, label: 'max', color: 'down' }] : []}
              series={[{ id: 'dd', label: 'Drawdown', type: 'area', color: 'down', dates: data.series.dates, values: data.series.drawdown, format: 'percent' }]}
            />
          </AnalysisSection>

          <AnalysisSection
            title="Rolling 63-day volatility (annualized)"
            what={
              <>
                How much the daily price swings over the trailing 63 trading days (about three months), scaled to a yearly figure. Rising volatility
                means larger daily moves in either direction; the dashed line is the volatility of the whole window for comparison. The line starts
                once 63 days of returns are available.
              </>
            }
            reading={volatilityReading(data)}
            aside={
              <StatList
                rows={[
                  { label: 'Volatility (whole window)', value: pct(data.performance.annualized_volatility) },
                  { label: 'Sharpe ratio', value: num(data.performance.sharpe_ratio), tone: tone(data.performance.sharpe_ratio), hint: 'Excess return per unit of total volatility' },
                  { label: 'Sortino ratio', value: num(data.performance.sortino_ratio), tone: tone(data.performance.sortino_ratio), hint: 'Excess return per unit of downside volatility' },
                  { label: 'Risk-free rate used', value: pct(data.risk_free_rate, 2) },
                ]}
              />
            }
          >
            <TimeSeriesChart
              ariaLabel="Rolling volatility"
              height={240}
              referenceLines={isNum(data.performance.annualized_volatility) ? [{ value: data.performance.annualized_volatility, label: 'window', color: 'warn' }] : []}
              series={[{ id: 'vol', label: 'Volatility', type: 'line', color: 'warn', dates: data.series.dates, values: data.series.rolling_volatility, format: 'percent' }]}
            />
          </AnalysisSection>

          {data.relative ? (
            <AnalysisSection
              title={`Relative to ${data.benchmark}`}
              what={
                <>
                  <strong>Beta</strong> measures how strongly {data.symbol} moved with {data.benchmark}: 1.0 means one-for-one, above 1 means amplified
                  moves, below 1 means damped moves. <strong>Correlation</strong> (−1 to 1) says how consistently they moved together. The chart shows
                  beta re-estimated over each trailing 63-day window, so you can see whether the relationship is stable.
                </>
              }
              reading={betaReading(data) ?? undefined}
              aside={
                <StatList
                  rows={[
                    { label: `Beta vs ${data.benchmark}`, value: num(data.relative.beta) },
                    { label: 'Correlation', value: num(data.relative.correlation) },
                    { label: 'R²', value: num(data.relative.r_squared), hint: 'Share of daily variance explained by the benchmark' },
                    { label: 'Alpha (annualized)', value: pct(data.relative.alpha), tone: tone(data.relative.alpha), hint: 'Jensen alpha, historical; not a forecast' },
                    { label: 'Tracking error', value: pct(data.relative.tracking_error), hint: 'Annualized volatility of the return difference' },
                    { label: 'Information ratio', value: num(data.relative.information_ratio), tone: tone(data.relative.information_ratio) },
                  ]}
                />
              }
            >
              {data.comparison && (
                <TimeSeriesChart
                  ariaLabel="Rolling beta"
                  height={220}
                  referenceLines={[{ value: 1, label: 'β = 1' }]}
                  series={[
                    { id: 'beta', label: 'Rolling beta', type: 'line', color: 'synthetic', dates: data.comparison.dates, values: data.comparison.rolling_beta, format: 'ratio' },
                  ]}
                />
              )}
            </AnalysisSection>
          ) : (
            <Notes tone="info" items={[`Relative metrics versus ${data.benchmark} are unavailable for this window.`]} />
          )}

          <AnalysisSection
            title="Distribution of daily returns"
            what={
              <>
                Every daily return in the window, grouped into buckets. A tall, narrow shape means steady day-to-day moves; long tails mean
                occasional large jumps. The left tail is the downside risk that <strong>Value at Risk</strong> and <strong>expected shortfall</strong>{' '}
                summarize.
              </>
            }
            reading={tailReading(data)}
            aside={
              <StatList
                rows={[
                  { label: '1-day VaR 95%', value: pct(data.performance.var_95), tone: 'text-down', hint: '5th percentile of daily returns' },
                  { label: '1-day CVaR 95%', value: pct(data.performance.cvar_95), tone: 'text-down', hint: 'Average of returns at or below VaR' },
                  { label: 'Best day', value: pct(data.performance.best_period, 2, true), tone: 'text-up' },
                  { label: 'Worst day', value: pct(data.performance.worst_period, 2), tone: 'text-down' },
                  { label: 'Days up', value: pct(data.performance.positive_periods_ratio, 0) },
                ]}
              />
            }
          >
            <ReturnDistribution returns={data.series.daily_returns} varValue={data.performance.var_95} />
          </AnalysisSection>

          <p className="border-t border-line pt-3 text-2xs text-ink-faint">
            All figures are computed by the ARGUS quant engine from dividend-adjusted daily closes; the written readings only restate those
            numbers. Undefined metrics show {DASH} rather than a misleading zero. Historical statistics describe the past and do not predict
            future returns. Hover the <Info className="inline h-3 w-3" aria-hidden /> icons for each formula.
          </p>
        </div>
      )}
    </div>
  );
}
