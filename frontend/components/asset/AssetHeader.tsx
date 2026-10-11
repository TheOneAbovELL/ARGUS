'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { BrainCircuit, Plus, Star } from 'lucide-react';
import { api, ApiError, describeError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { compact, count, currencySymbol, DASH, pct, price } from '@/lib/format';
import type { Profile, Quote, Technicals } from '@/lib/types';
import DataBadge from '@/components/DataBadge';
import { Skeleton } from '@/components/ui';

const last = <T,>(xs: T[]): T | undefined => xs[xs.length - 1];
const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

function WatchButton({ symbol }: { symbol: string }) {
  const { user } = useAuth();
  const [watching, setWatching] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    api
      .watchlist()
      .then((items) => setWatching(items.some((i) => i.symbol === symbol)))
      .catch(() => setWatching(null));
  }, [user, symbol]);

  if (!user)
    return (
      <Link href="/login" className="btn-ghost" title="Sign in to keep a watchlist">
        <Star className="h-3.5 w-3.5" aria-hidden /> Watch
      </Link>
    );

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      if (watching) await api.unwatch(symbol);
      else await api.watch(symbol);
      setWatching(!watching);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <button type="button" onClick={toggle} disabled={busy || watching === null} className="btn-ghost" aria-pressed={!!watching} title={error ?? undefined}>
      <Star className={`h-3.5 w-3.5 ${watching ? 'fill-warn text-warn' : ''}`} aria-hidden />
      {watching ? 'Watching' : 'Watch'}
    </button>
  );
}

/** Horizontal low–high range with a marker at the current value. */
function RangeBar({ low, high, value, label }: { low: number | null; high: number | null; value: number | null; label: string }) {
  if (!isNum(low) || !isNum(high) || !isNum(value) || high <= low) return <span className="num text-ink">{DASH}</span>;
  const position = Math.min(1, Math.max(0, (value - low) / (high - low)));
  return (
    <div className="w-40" aria-label={`${label}: ${price(low)} to ${price(high)}, current ${price(value)}`}>
      <div className="num flex justify-between text-[13px] text-ink">
        <span>{price(low)}</span>
        <span>{price(high)}</span>
      </div>
      <div className="relative mt-1 h-1 rounded-full bg-line">
        <div className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-down/70 via-warn/60 to-up/70" style={{ width: '100%' }} />
        <div className="absolute -top-1 h-3 w-0.5 rounded bg-ink" style={{ left: `calc(${position * 100}% - 1px)` }} aria-hidden />
      </div>
    </div>
  );
}

function Stat({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div className="min-w-0" title={hint}>
      <dt className="text-xs text-ink-faint">{label}</dt>
      <dd className="mt-0.5">{children}</dd>
    </div>
  );
}

export default function AssetHeader({
  symbol,
  quote,
  quoteError,
  profile,
  chart,
}: {
  symbol: string;
  quote: Quote | null;
  quoteError: unknown;
  profile: Profile | null;
  chart: Technicals | null;
}) {
  const name = quote?.name ?? profile?.name;
  const exchange = quote?.exchange ?? profile?.exchange;
  const currency = quote?.currency ?? profile?.currency ?? chart?.currency ?? null;
  const stat = (key: string) => profile?.stats.find((s) => s.key === key)?.value ?? null;

  const lastBar = chart
    ? {
        date: last(chart.dates),
        open: last(chart.open) ?? null,
        high: last(chart.high) ?? null,
        low: last(chart.low) ?? null,
        volume: last(chart.volume) ?? null,
        avgVolume: last(chart.indicators.volume_sma20) ?? null,
      }
    : null;
  const hasOhlc = !!lastBar && isNum(lastBar.open) && isNum(lastBar.high) && isNum(lastBar.low) && lastBar.high !== lastBar.low;

  return (
    <header className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight text-ink">{symbol}</h1>
            {exchange && <span className="chip border-line text-ink-muted">{exchange}</span>}
            {profile?.quote_type && <span className="chip border-line text-ink-faint">{profile.quote_type}</span>}
          </div>
          {name ? <p className="mt-0.5 truncate text-[13px] text-ink-muted">{name}</p> : <Skeleton className="mt-1 h-4 w-48" />}
          <div className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            {quote ? (
              <>
                <span className="num text-[28px] font-semibold leading-none text-ink">
                  {currencySymbol(currency)}
                  {price(quote.price)}
                </span>
                {!currencySymbol(currency) && <span className="text-[13px] text-ink-faint">{currency}</span>}
                <span className={`num text-[15px] font-medium ${quote.change === null ? 'text-ink-muted' : quote.change >= 0 ? 'text-up' : 'text-down'}`}>
                  {quote.change !== null ? `${quote.change >= 0 ? '+' : ''}${quote.change.toFixed(2)}` : ''} ({pct(quote.change_percent, 2, true)})
                </span>
                <DataBadge provenance={quote.provenance} showProvider />
              </>
            ) : quoteError ? (
              <span className="text-[13px] text-ink-muted">
                {quoteError instanceof ApiError && quoteError.code === 'symbol_not_found'
                  ? 'No current quote available; history and analytics may still work.'
                  : `Quote unavailable: ${describeError(quoteError)}`}
              </span>
            ) : (
              <Skeleton className="h-8 w-56" />
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <WatchButton symbol={symbol} />
          <Link href={`/portfolio?add=${encodeURIComponent(symbol)}`} className="btn-ghost">
            <Plus className="h-3.5 w-3.5" aria-hidden /> Add to portfolio
          </Link>
          <Link href={`/research?symbol=${encodeURIComponent(symbol)}`} className="btn-primary">
            <BrainCircuit className="h-3.5 w-3.5" aria-hidden /> Research report
          </Link>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 border-y border-line py-3 sm:grid-cols-3 lg:grid-cols-[repeat(4,minmax(0,auto))_auto_auto_repeat(3,minmax(0,auto))] lg:justify-between">
        <Stat label="Prev. close">
          <span className="num text-[13px] text-ink">{price(quote?.previous_close)}</span>
        </Stat>
        <Stat label={`Open${lastBar?.date ? ` (${lastBar.date})` : ''}`} hint="Latest daily bar">
          <span className="num text-[13px] text-ink">{hasOhlc ? price(lastBar!.open) : DASH}</span>
        </Stat>
        <Stat label="Volume" hint="Latest session vs its 20-day average">
          <span className="num text-[13px] text-ink">{count(lastBar?.volume ?? null, currency)}</span>
          {isNum(lastBar?.volume) && isNum(lastBar?.avgVolume) && lastBar!.avgVolume! > 0 && (
            <span className="num ml-1.5 text-xs text-ink-faint">{(lastBar!.volume! / lastBar!.avgVolume!).toFixed(2)}× avg</span>
          )}
        </Stat>
        <Stat label="Avg. volume (20d)">
          <span className="num text-[13px] text-ink">{count(lastBar?.avgVolume ?? null, currency)}</span>
        </Stat>
        <Stat label="Day range" hint="Low and high of the latest daily bar">
          {hasOhlc ? <RangeBar label="Day range" low={lastBar!.low} high={lastBar!.high} value={quote?.price ?? last(chart!.close) ?? null} /> : <span className="num text-ink">{DASH}</span>}
        </Stat>
        <Stat label="52-week range">
          <RangeBar label="52-week range" low={chart?.low_52w ?? null} high={chart?.high_52w ?? null} value={quote?.price ?? chart?.last_close ?? null} />
        </Stat>
        <Stat label="Market cap">
          <span className="num text-[13px] text-ink">{compact(stat('market_cap'), currency)}</span>
        </Stat>
        <Stat label="P/E (TTM)" hint="Provider-reported; not recomputed by ARGUS">
          <span className="num text-[13px] text-ink">{isNum(stat('trailing_pe')) ? stat('trailing_pe')!.toFixed(2) : DASH}</span>
        </Stat>
        <Stat label="Dividend yield" hint="Provider-reported">
          <span className="num text-[13px] text-ink">{pct(stat('dividend_yield'))}</span>
        </Stat>
      </dl>
    </header>
  );
}
