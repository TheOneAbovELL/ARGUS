'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ShieldAlert } from 'lucide-react';
import { api } from '@/lib/api';
import { num, pct, shortDate, signClass } from '@/lib/format';
import { correlationReading, portfolioDrawdownReading, portfolioGrowthReading, riskAllocationReading, stressReading } from '@/lib/narratives';
import type { HoldingInput, PortfolioAnalysis, StressResult } from '@/lib/types';
import TimeSeriesChart from '@/components/charts/TimeSeriesChart';
import Heatmap from '@/components/charts/Heatmap';
import BarRows from '@/components/charts/BarRows';
import KeyFigure, { KeyFigures } from '@/components/KeyFigure';
import DataBadge from '@/components/DataBadge';
import { AnalysisSection, ErrorNotice, LoadingBlock, Notes, StatList } from '@/components/ui';

const isNum = (v: number | null | undefined): v is number => typeof v === 'number' && Number.isFinite(v);
const tone = (v: number | null | undefined) => (!isNum(v) || v === 0 ? undefined : v > 0 ? 'text-up' : 'text-down');

function StressSection({ holdings, benchmark }: { holdings: HoldingInput[]; benchmark: string }) {
  const [result, setResult] = useState<StressResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(await api.stressPortfolio({ holdings, benchmark }));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };
  return (
    <AnalysisSection
      title="Historical stress episodes"
      what={
        <>
          Replays today&apos;s weights through named historical sell-offs (the 2008 financial crisis, 2011, Q4 2018, the 2020 COVID crash and
          2022) using the actual adjusted prices of each holding. It answers &quot;what would this mix have done then&quot;, not what it will do next
          time.
        </>
      }
      reading={result ? stressReading(result) ?? undefined : undefined}
      aside={
        <button type="button" className="btn-ghost" onClick={run} disabled={loading}>
          <ShieldAlert className="h-3.5 w-3.5" aria-hidden /> {result ? 'Re-run' : 'Run stress test'}
        </button>
      }
    >
      {loading && <LoadingBlock rows={4} label="Replaying episodes" />}
      {error ? <ErrorNotice error={error} onRetry={run} /> : null}
      {result && (
        <div className="overflow-x-auto">
          <table className="table-terminal min-w-[560px]">
            <thead>
              <tr>
                <th>Episode</th>
                <th className="text-right">Portfolio</th>
                <th className="text-right">{result.benchmark}</th>
                <th className="text-right">Difference</th>
                <th className="text-right">Worst drawdown</th>
              </tr>
            </thead>
            <tbody>
              {result.episodes.map((e) => {
                const diff = isNum(e.portfolio_return) && isNum(e.benchmark_return) ? e.portfolio_return - e.benchmark_return : null;
                return (
                  <tr key={e.key} className="align-top">
                    <td>
                      <p className="text-ink">{e.name}</p>
                      <p className="num text-2xs text-ink-faint">
                        {shortDate(e.start)} – {shortDate(e.end)}
                      </p>
                      {!e.computable && (
                        <p className="text-2xs text-warn">Not computable{e.missing_symbols.length ? `: no history for ${e.missing_symbols.join(', ')}` : ''}</p>
                      )}
                    </td>
                    <td className={`num text-right ${signClass(e.portfolio_return)}`}>{pct(e.portfolio_return, 1)}</td>
                    <td className={`num text-right ${signClass(e.benchmark_return)}`}>{pct(e.benchmark_return, 1)}</td>
                    <td className={`num text-right ${signClass(diff)}`}>{diff === null ? '—' : pct(diff, 1, true)}</td>
                    <td className="num text-right text-down">{pct(e.portfolio_max_drawdown, 1)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-2 text-2xs text-ink-faint">{result.method}</p>
        </div>
      )}
    </AnalysisSection>
  );
}

export default function PortfolioResults({ analysis, holdings }: { analysis: PortfolioAnalysis; holdings: HoldingInput[] }) {
  const a = analysis;
  const p = a.performance;
  const r = a.relative;
  const modelLabel = a.model === 'buy_and_hold' ? 'Buy-and-hold (weights drift)' : 'Daily rebalanced to target weights';
  const unit = a.periods_per_year === 365 ? 'days' : 'trading days';
  const riskText = riskAllocationReading(a);
  const corrText = correlationReading(a);
  return (
    <div className="space-y-10">
      {a.warnings.length > 0 && <Notes title="Data and calculation notes" items={a.warnings} />}

      <section aria-label="Portfolio summary" className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="section-title">Portfolio summary</h2>
            <p className="text-xs text-ink-faint">
              {modelLabel} · {shortDate(a.start)} – {shortDate(a.end)} · benchmark {a.benchmark}
            </p>
          </div>
          <span className="flex flex-wrap gap-1">
            {Array.from(new Set(Object.values(a.provenance).map((x) => x.mode))).map((mode) => {
              const sample = Object.values(a.provenance).find((x) => x.mode === mode)!;
              return <DataBadge key={mode} provenance={sample} />;
            })}
          </span>
        </div>
        <KeyFigures>
          <KeyFigure metric="total_return" label="Total return" value={pct(p.total_return)} toneClass={tone(p.total_return)} sub={`${p.observations} daily returns`} />
          <KeyFigure metric="annualized_return" label="Annualized return" value={pct(p.annualized_return)} toneClass={tone(p.annualized_return)} />
          <KeyFigure metric="annualized_volatility" label="Annualized volatility" value={pct(p.annualized_volatility)} />
          <KeyFigure
            metric="sharpe_ratio"
            label="Sharpe ratio"
            value={num(p.sharpe_ratio)}
            toneClass={tone(p.sharpe_ratio)}
            sub={isNum(p.sharpe_ratio) ? `risk-free ${pct(a.risk_free_rate, 2)}` : 'undefined for this window'}
          />
          <KeyFigure
            metric="max_drawdown"
            label="Max drawdown"
            value={pct(p.max_drawdown)}
            toneClass={p.max_drawdown < 0 ? 'text-down' : undefined}
            sub={`${shortDate(p.max_drawdown_peak)} → ${shortDate(p.max_drawdown_trough)}`}
          />
          <KeyFigure metric="beta" label={`Beta vs ${a.benchmark}`} value={num(r?.beta)} sub={r ? `correlation ${num(r.correlation)}` : 'unavailable'} />
        </KeyFigures>
      </section>

      <AnalysisSection
        title={`Growth vs ${a.benchmark}`}
        what={
          <>
            Cumulative return of the portfolio (blue) and {a.benchmark} (orange) from the first common date, both starting at 0%. The portfolio line
            follows the selected rebalancing model; switching between daily rebalancing and buy-and-hold changes it on purpose.
          </>
        }
        reading={portfolioGrowthReading(a)}
        aside={
          <StatList
            rows={[
              { label: 'Portfolio annualized', value: pct(p.annualized_return), tone: tone(p.annualized_return) },
              ...(r
                ? [
                    { label: `${a.benchmark} annualized`, value: pct(r.benchmark_annualized_return), tone: tone(r.benchmark_annualized_return) },
                    { label: 'Excess (annualized)', value: pct(r.excess_annualized_return, 2, true), tone: tone(r.excess_annualized_return) },
                    { label: 'Alpha (annualized)', value: pct(r.alpha), tone: tone(r.alpha), hint: 'Jensen alpha, historical; not a forecast' },
                    { label: 'Tracking error', value: pct(r.tracking_error) },
                  ]
                : []),
              { label: 'Sortino ratio', value: num(p.sortino_ratio), tone: tone(p.sortino_ratio) },
            ]}
          />
        }
      >
        <TimeSeriesChart
          ariaLabel="Portfolio cumulative return versus benchmark"
          height={320}
          referenceLines={[{ value: 0, label: 'start' }]}
          series={
            a.series.benchmark_dates.length
              ? [
                  { id: 'p', label: 'Portfolio', type: 'line', color: 'accent', dates: a.series.benchmark_dates, values: a.series.portfolio_cumulative_on_benchmark_dates, format: 'percent' },
                  { id: 'b', label: a.benchmark, type: 'line', color: 'chart-1', dates: a.series.benchmark_dates, values: a.series.benchmark_cumulative_return, format: 'percent', lineWidth: 1 },
                ]
              : [{ id: 'p', label: 'Portfolio', type: 'line', color: 'accent', dates: a.series.dates, values: a.series.cumulative_return, format: 'percent' }]
          }
        />
      </AnalysisSection>

      <AnalysisSection
        title="Drawdown"
        what="How far the portfolio's value sat below its previous high on each day. The depth shows the worst loss from a peak; the width shows how long it took to recover."
        reading={portfolioDrawdownReading(a)}
        aside={
          <StatList
            rows={[
              { label: 'Max drawdown', value: pct(p.max_drawdown), tone: p.max_drawdown < 0 ? 'text-down' : undefined },
              { label: 'Recovered', value: p.max_drawdown_recovery ? shortDate(p.max_drawdown_recovery) : 'Not yet' },
              { label: 'Longest underwater', value: `${p.longest_drawdown_days} ${unit}` },
              { label: '1-day VaR 95%', value: pct(p.var_95), tone: 'text-down' },
              { label: '1-day CVaR 95%', value: pct(p.cvar_95), tone: 'text-down' },
            ]}
          />
        }
      >
        <TimeSeriesChart
          ariaLabel="Portfolio drawdown"
          height={220}
          referenceLines={p.max_drawdown < 0 ? [{ value: p.max_drawdown, label: 'max', color: 'down' }] : []}
          series={[{ id: 'dd', label: 'Drawdown', type: 'area', color: 'down', dates: a.series.dates, values: a.series.drawdown, format: 'percent' }]}
        />
      </AnalysisSection>

      <AnalysisSection
        title="Capital vs risk allocation"
        what={
          <>
            Blue bars show how the money is split (target weights). Red bars show how much of the portfolio&apos;s total volatility each holding is
            responsible for, after accounting for how the holdings move together. A volatile holding can dominate risk even with a small weight.
          </>
        }
        reading={riskText ?? undefined}
      >
        <BarRows
          legend={[
            { key: 'w', label: 'Target weight', color: 'accent' },
            { key: 'r', label: 'Share of portfolio volatility', color: 'down' },
          ]}
          rows={a.assets.map((asset) => ({
            label: asset.symbol,
            values: [
              { key: 'w', value: asset.weight, color: 'accent' },
              { key: 'r', value: asset.risk_contribution, color: 'down' },
            ],
          }))}
        />
        <p className="mt-3 text-2xs text-ink-faint">Risk contribution = wᵢ·(Σw)ᵢ / σₚ²; contributions sum to 100% and can be negative for hedging assets.</p>
      </AnalysisSection>

      <AnalysisSection
        title="Correlation of daily returns"
        what={
          <>
            How closely each pair of holdings moved day to day, from −1 (opposite) through 0 (unrelated) to +1 (in lockstep). Low or negative
            correlations are what make a portfolio less volatile than its parts.
          </>
        }
        reading={corrText ?? undefined}
        aside={
          <StatList
            rows={[{ label: 'Diversification ratio', value: num(a.diversification_ratio), hint: 'Σ wᵢσᵢ / σₚ — above 1 means diversification is reducing risk' }]}
          />
        }
      >
        <Heatmap labels={a.correlation_symbols} matrix={a.correlation} />
      </AnalysisSection>

      <section aria-label="Holdings breakdown" className="space-y-2 border-t border-line pt-6">
        <h2 className="section-title">Holdings breakdown</h2>
        <p className="prose-explain">
          Per-holding figures over the same window. End weight shows where buy-and-hold weights drifted to; return contribution is each
          holding&apos;s share of the portfolio&apos;s total return.
        </p>
        <div className="overflow-x-auto">
          <table className="table-terminal min-w-[760px]">
            <thead>
              <tr>
                <th>Instrument</th>
                <th className="text-right">Weight</th>
                <th className="text-right">End weight</th>
                <th className="text-right">Total return</th>
                <th className="text-right">Ann. return</th>
                <th className="text-right">Volatility</th>
                <th className="text-right">Beta</th>
                <th className="text-right">Return contrib.</th>
                <th className="text-right">Risk contrib.</th>
              </tr>
            </thead>
            <tbody className="num">
              {a.assets.map((asset) => (
                <tr key={asset.symbol}>
                  <td>
                    <Link href={`/asset?symbol=${encodeURIComponent(asset.symbol)}`} className="font-medium text-ink hover:text-accent">
                      {asset.symbol}
                    </Link>
                  </td>
                  <td className="text-right">{pct(asset.weight, 1)}</td>
                  <td className="text-right text-ink-muted">{pct(asset.ending_weight, 1)}</td>
                  <td className={`text-right ${signClass(asset.total_return)}`}>{pct(asset.total_return, 1)}</td>
                  <td className={`text-right ${signClass(asset.annualized_return)}`}>{pct(asset.annualized_return, 1)}</td>
                  <td className="text-right">{pct(asset.annualized_volatility, 1)}</td>
                  <td className="text-right">{num(asset.beta)}</td>
                  <td className={`text-right ${signClass(asset.return_contribution)}`}>{pct(asset.return_contribution, 2)}</td>
                  <td className="text-right">{pct(asset.risk_contribution, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-2xs text-ink-faint">Return contribution: {a.contribution_method}.</p>
      </section>

      <StressSection holdings={holdings} benchmark={a.benchmark} />
      <Notes tone="info" title="Assumptions" items={a.assumptions} />
    </div>
  );
}
