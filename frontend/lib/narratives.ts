// Plain-language readings of backend analytics. These functions only restate
// numbers the quant engine already computed (and pick the latest/extreme point
// of a backend series); they never derive new financial metrics.

import type { AssetAnalysis, Performance, PortfolioAnalysis, StressResult } from './types';
import { pct, shortDate } from './format';

const isNum = (v: number | null | undefined): v is number => typeof v === 'number' && Number.isFinite(v);

function lastValid(values: (number | null)[]): { value: number; index: number } | null {
  for (let i = values.length - 1; i >= 0; i--) {
    const v = values[i];
    if (isNum(v)) return { value: v, index: i };
  }
  return null;
}

function extreme(values: (number | null)[], kind: 'max' | 'min'): { value: number; index: number } | null {
  let best: { value: number; index: number } | null = null;
  values.forEach((v, index) => {
    if (!isNum(v)) return;
    if (!best || (kind === 'max' ? v > best.value : v < best.value)) best = { value: v, index };
  });
  return best;
}

const abs = (v: number) => pct(Math.abs(v), 1);

export function returnsReading(a: AssetAnalysis): string {
  const p = a.performance;
  const r = a.relative;
  const base = `Over ${shortDate(a.series.dates[0])} – ${shortDate(a.series.dates[a.series.dates.length - 1])}, ${a.symbol} ${
    p.total_return >= 0 ? 'gained' : 'lost'
  } ${abs(p.total_return)} in total${isNum(p.annualized_return) ? ` (${pct(p.annualized_return, 1, true)} a year)` : ''}, dividends reinvested.`;
  if (!r) return base;
  const bench = `${a.benchmark} ${r.benchmark_total_return >= 0 ? 'gained' : 'lost'} ${abs(r.benchmark_total_return)} over the dates both traded`;
  const excess = isNum(r.excess_annualized_return)
    ? `, so ${a.symbol} ${r.excess_annualized_return >= 0 ? 'outperformed' : 'underperformed'} by ${abs(r.excess_annualized_return)} a year.`
    : '.';
  return `${base} ${bench}${excess}`;
}

function drawdownText(label: string, p: Performance, periodsPerYear: number): string {
  if (p.max_drawdown === 0) return `${label} never closed below a previous high in this window.`;
  const unit = periodsPerYear === 365 ? 'days' : 'trading days';
  const recovery = p.max_drawdown_recovery
    ? `It regained that high on ${shortDate(p.max_drawdown_recovery)}.`
    : p.current_drawdown < 0
      ? `It has not recovered: the last close is still ${abs(p.current_drawdown)} below its running peak.`
      : 'It has not regained that high.';
  return `The worst decline was ${abs(p.max_drawdown)}, from the peak on ${shortDate(p.max_drawdown_peak)} to the low on ${shortDate(
    p.max_drawdown_trough,
  )}. ${recovery} The longest stretch spent below a previous high was ${p.longest_drawdown_days} ${unit}.`;
}

export function drawdownReading(a: AssetAnalysis): string {
  return drawdownText(a.symbol, a.performance, a.periods_per_year);
}

export function volatilityReading(a: AssetAnalysis): string {
  const p = a.performance;
  const current = lastValid(a.series.rolling_volatility);
  const peak = extreme(a.series.rolling_volatility, 'max');
  if (!current || !isNum(p.annualized_volatility)) return 'Not enough history to show rolling volatility for this window.';
  const direction = current.value > p.annualized_volatility ? 'higher than' : 'lower than';
  const peakText = peak ? ` It peaked at ${pct(peak.value, 1)} around ${shortDate(a.series.dates[peak.index])}.` : '';
  return `Recent (63-day) volatility is ${pct(current.value, 1)} a year, ${direction} the ${pct(
    p.annualized_volatility,
    1,
  )} measured over the whole window.${peakText} For scale, broad equity indices have typically run around 15–20%.`;
}

export function betaReading(a: AssetAnalysis): string | null {
  const r = a.relative;
  if (!r || !isNum(r.beta)) return null;
  const rolling = a.comparison ? lastValid(a.comparison.rolling_beta) : null;
  const meaning =
    r.beta > 1.05
      ? `amplified ${a.benchmark}'s moves (a 1% benchmark move came with about ${r.beta.toFixed(2)}% on average)`
      : r.beta < 0.95 && r.beta >= 0
        ? `moved less than ${a.benchmark} (about ${r.beta.toFixed(2)}% per 1% benchmark move on average)`
        : r.beta < 0
          ? `tended to move against ${a.benchmark}`
          : `moved roughly in line with ${a.benchmark}`;
  const corr = isNum(r.correlation)
    ? ` Correlation of ${r.correlation.toFixed(2)} means ${
        Math.abs(r.correlation) >= 0.7 ? 'the benchmark explains much' : Math.abs(r.correlation) >= 0.4 ? 'the benchmark explains part' : 'the benchmark explains little'
      } of its day-to-day movement.`
    : '';
  const recent = rolling ? ` Over the last 63 trading days beta was ${rolling.value.toFixed(2)}.` : '';
  return `Over the window ${a.symbol} ${meaning}.${corr}${recent}`;
}

export function tailReading(a: AssetAnalysis): string {
  const p = a.performance;
  const parts: string[] = [];
  if (isNum(p.var_95)) {
    parts.push(`On the worst 5% of days, ${a.symbol} fell ${abs(p.var_95)} or more (1-day historical VaR at 95%).`);
  }
  if (isNum(p.cvar_95)) parts.push(`On those days the average loss was ${abs(p.cvar_95)} (expected shortfall).`);
  parts.push(
    `The best day was ${pct(p.best_period, 1, true)}, the worst ${pct(p.worst_period, 1)}, and ${pct(
      p.positive_periods_ratio,
      0,
    )} of days closed higher.`,
  );
  return parts.join(' ');
}

// ---- Portfolio ---------------------------------------------------------------

export function portfolioGrowthReading(a: PortfolioAnalysis): string {
  const p = a.performance;
  const r = a.relative;
  const base = `From ${shortDate(a.start)} to ${shortDate(a.end)} the portfolio ${p.total_return >= 0 ? 'gained' : 'lost'} ${abs(
    p.total_return,
  )}${isNum(p.annualized_return) ? ` (${pct(p.annualized_return, 1, true)} a year)` : ''} with ${
    isNum(p.annualized_volatility) ? `${pct(p.annualized_volatility, 1)} annualized volatility` : 'undefined volatility'
  }.`;
  if (!r) return base;
  const excess = isNum(r.excess_annualized_return)
    ? ` That is ${abs(r.excess_annualized_return)} a year ${r.excess_annualized_return >= 0 ? 'ahead of' : 'behind'} ${a.benchmark} (${pct(
        r.benchmark_annualized_return,
        1,
        true,
      )} a year).`
    : '';
  return base + excess;
}

export function portfolioDrawdownReading(a: PortfolioAnalysis): string {
  return drawdownText('The portfolio', a.performance, a.periods_per_year);
}

export function riskAllocationReading(a: PortfolioAnalysis): string | null {
  const assets = a.assets.filter((x) => isNum(x.risk_contribution));
  if (!assets.length) return null;
  const top = assets.reduce((best, x) => ((x.risk_contribution as number) > (best.risk_contribution as number) ? x : best));
  const topRisk = top.risk_contribution as number;
  const ratio = top.weight > 0 ? topRisk / top.weight : null;
  const parts = [
    `${top.symbol} is ${pct(top.weight, 0)} of the capital but ${pct(topRisk, 0)} of the portfolio's volatility${
      ratio !== null && ratio > 1.2 ? ', so it drives risk more than its weight suggests' : ''
    }.`,
  ];
  const hedges = assets.filter((x) => (x.risk_contribution as number) < 0).map((x) => x.symbol);
  if (hedges.length) parts.push(`${hedges.join(', ')} had a negative risk contribution: ${hedges.length > 1 ? 'they' : 'it'} offset part of the other holdings' moves.`);
  return parts.join(' ');
}

export function correlationReading(a: PortfolioAnalysis): string | null {
  const pairs: { a: string; b: string; v: number }[] = [];
  a.correlation.forEach((row, i) =>
    row.forEach((v, j) => {
      if (j > i && isNum(v)) pairs.push({ a: a.correlation_symbols[i], b: a.correlation_symbols[j], v });
    }),
  );
  if (!pairs.length) return null;
  const hi = pairs.reduce((m, x) => (x.v > m.v ? x : m));
  const lo = pairs.reduce((m, x) => (x.v < m.v ? x : m));
  const parts = [
    hi.v < 0.3
      ? `Every pair has a low correlation; even the most similar, ${hi.a} and ${hi.b}, is only ${hi.v.toFixed(2)}.`
      : `The most similar pair is ${hi.a} and ${hi.b} (${hi.v.toFixed(2)})${hi.v >= 0.8 ? ': they largely move together, so holding both adds little diversification' : ''}.`,
  ];
  if (lo !== hi && hi.v >= 0.3) {
    parts.push(`The least similar is ${lo.a} and ${lo.b} (${lo.v.toFixed(2)})${lo.v < 0.3 ? ', which is where most of the diversification comes from' : ''}.`);
  }
  if (isNum(a.diversification_ratio)) {
    parts.push(
      `The diversification ratio is ${a.diversification_ratio.toFixed(2)}: the portfolio's volatility is ${pct(
        1 - 1 / a.diversification_ratio,
        0,
      )} lower than the weighted average of its holdings' volatilities.`,
    );
  }
  return parts.join(' ');
}

export function stressReading(s: StressResult): string | null {
  const done = s.episodes.filter((e) => e.computable && isNum(e.portfolio_return));
  if (!done.length) return null;
  const worst = done.reduce((m, e) => ((e.portfolio_return as number) < (m.portfolio_return as number) ? e : m));
  const beat = done.filter((e) => isNum(e.benchmark_return) && (e.portfolio_return as number) > (e.benchmark_return as number)).length;
  const comparable = done.filter((e) => isNum(e.benchmark_return)).length;
  return `The hardest episode for these weights was ${worst.name}: ${pct(worst.portfolio_return, 1)}${
    isNum(worst.benchmark_return) ? ` versus ${pct(worst.benchmark_return, 1)} for ${s.benchmark}` : ''
  }. The portfolio held up better than ${s.benchmark} in ${beat} of ${comparable} episodes with data for both.`;
}
