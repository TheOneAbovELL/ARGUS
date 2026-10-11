'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import { useAsync } from '@/lib/useAsync';
import { normalizeSymbol, type Period } from '@/lib/format';
import { pushRecent, readRecent } from '@/lib/recent';
import type { Profile, Quote, Technicals } from '@/lib/types';
import SymbolSearch from '@/components/SymbolSearch';
import AssetHeader from '@/components/asset/AssetHeader';
import ChartSection from '@/components/asset/ChartSection';
import TechnicalSummary from '@/components/asset/TechnicalSummary';
import ProfilePanel from '@/components/asset/ProfilePanel';
import AnalyticsPanel from '@/components/asset/AnalyticsPanel';
import NewsPanel from '@/components/asset/NewsPanel';
import FilingsPanel from '@/components/FilingsPanel';
import { EmptyState, LoadingBlock, Skeleton, Tabs } from '@/components/ui';

type Tab = 'overview' | 'analytics' | 'news' | 'filings';
const TABS = [
  { value: 'overview', label: 'Chart & technicals' },
  { value: 'analytics', label: 'Performance & risk' },
  { value: 'news', label: 'News' },
  { value: 'filings', label: 'Filings' },
] as const;

function AssetView({ symbol }: { symbol: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const tab = (TABS.some((t) => t.value === params.get('tab')) ? params.get('tab') : 'overview') as Tab;
  const [period, setPeriod] = useState<Period>('1y');
  const quote = useAsync<Quote>(() => api.quote(symbol), [symbol]);
  const profile = useAsync<Profile>(() => api.profile(symbol), [symbol]);
  const chart = useAsync<Technicals>(() => api.technicals(symbol, period), [symbol, period]);

  useEffect(() => {
    pushRecent(symbol);
    document.title = `${symbol} · ARGUS`;
  }, [symbol]);

  const setTab = (next: Tab) => router.replace(`/asset?symbol=${encodeURIComponent(symbol)}${next === 'overview' ? '' : `&tab=${next}`}`, { scroll: false });

  return (
    <div className="space-y-5">
      <AssetHeader symbol={symbol} quote={quote.data} quoteError={quote.error} profile={profile.data} chart={chart.data} />
      <Tabs label="Asset sections" options={TABS} value={tab} onChange={setTab} />
      {tab === 'overview' && (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="min-w-0 space-y-6">
            <ChartSection
              symbol={symbol}
              period={period}
              onPeriod={setPeriod}
              data={chart.data}
              error={chart.error}
              loading={chart.loading}
              onRetry={chart.reload}
            />
            <NewsPanel symbol={symbol} limit={5} />
          </div>
          <aside className="space-y-8">
            {chart.data ? <TechnicalSummary data={chart.data} /> : chart.loading ? <LoadingBlock rows={6} /> : null}
            <ProfilePanel profile={profile.data} error={profile.error} loading={profile.loading} onRetry={profile.reload} />
          </aside>
        </div>
      )}
      {tab === 'analytics' && <AnalyticsPanel symbol={symbol} />}
      {tab === 'news' && <NewsPanel symbol={symbol} />}
      {tab === 'filings' && <FilingsPanel symbol={symbol} />}
    </div>
  );
}

function AssetLanding() {
  const [recent, setRecent] = useState<string[]>([]);
  useEffect(() => setRecent(readRecent()), []);
  return (
    <div className="mx-auto max-w-2xl space-y-6 pt-10">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Look up an asset</h1>
        <p className="mt-1 text-[13px] text-ink-muted">Stocks, ETFs, indices, currencies and crypto from NSE, BSE, NYSE, Nasdaq and more.</p>
      </div>
      <SymbolSearch autoFocus placeholder="Company or symbol — RELIANCE.NS, TCS.NS, AAPL, ^NSEI, BTC-USD" />
      {recent.length > 0 && (
        <div>
          <h2 className="mb-2 text-xs font-medium text-ink-faint">Recently viewed</h2>
          <div className="flex flex-wrap gap-2">
            {recent.map((s) => (
              <Link key={s} href={`/asset?symbol=${encodeURIComponent(s)}`} className="num rounded border border-line px-2.5 py-1 text-[13px] text-ink hover:border-accent">
                {s}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function AssetPageInner() {
  const params = useSearchParams();
  const raw = params.get('symbol');
  if (!raw) return <AssetLanding />;
  const symbol = normalizeSymbol(raw);
  if (!symbol)
    return (
      <EmptyState title={`"${raw}" is not a valid symbol`} action={<SymbolSearch />}>
        Symbols are 1-15 characters: letters, digits, and . - = ^
      </EmptyState>
    );
  return <AssetView key={symbol} symbol={symbol} />;
}

export default function AssetPage() {
  return (
    <Suspense fallback={<Skeleton className="h-10 w-64" />}>
      <AssetPageInner />
    </Suspense>
  );
}
