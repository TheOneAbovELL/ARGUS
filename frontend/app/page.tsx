'use client';

import Link from 'next/link';
import { useState } from 'react';
import { ArrowRight, BrainCircuit, FileText, LineChart, PieChart, RefreshCw, Star } from 'lucide-react';
import { api, describeError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useSystem } from '@/lib/system';
import { useAsync } from '@/lib/useAsync';
import { relativeTime } from '@/lib/format';
import type { QuoteResult, ResearchSummary } from '@/lib/types';
import DataBadge from '@/components/DataBadge';
import QuoteTable from '@/components/QuoteTable';
import SymbolSearch from '@/components/SymbolSearch';
import { EmptyState, ErrorNotice, LoadingBlock } from '@/components/ui';

const INDIA = ['^NSEI', '^BSESN', '^NSEBANK'];
const US = ['SPY', 'QQQ', 'IWM', 'TLT', 'GLD'];
const LABELS: Record<string, string> = {
  '^NSEI': 'NIFTY 50',
  '^BSESN': 'SENSEX',
  '^NSEBANK': 'NIFTY BANK',
  SPY: 'S&P 500',
  QQQ: 'Nasdaq-100',
  IWM: 'Russell 2000',
  TLT: '20y+ Treasuries',
  GLD: 'Gold',
};

/** Borderless block with a title row; sections separate by rules, not boxes. */
function Block({ title, actions, children, note }: { title: string; actions?: React.ReactNode; children: React.ReactNode; note?: React.ReactNode }) {
  return (
    <section aria-label={title} className="panel overflow-hidden">
      <header className="flex items-center justify-between gap-2 px-4 pb-1 pt-3">
        <h2 className="text-[13px] font-semibold text-ink">{title}</h2>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </header>
      {children}
      {note && <p className="border-t border-line/70 px-4 py-2 text-2xs leading-relaxed text-ink-faint">{note}</p>}
    </section>
  );
}

function MarketGroup({ title, results }: { title: string; results: QuoteResult[] }) {
  return (
    <div className="min-w-0">
      <h3 className="px-4 pt-2 text-xs font-medium text-ink-muted">{title}</h3>
      <QuoteTable results={results} labels={LABELS} />
    </div>
  );
}

function MarketPanel() {
  const { data, error, loading, reload } = useAsync<QuoteResult[]>(() => api.quotes([...INDIA, ...US]), []);
  const provenance = data?.find((r) => r.quote)?.quote?.provenance;
  return (
    <Block
      title="Market snapshot"
      actions={
        <>
          {provenance && <DataBadge provenance={provenance} showProvider />}
          <button type="button" onClick={reload} className="btn-tool" aria-label="Refresh market snapshot">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} aria-hidden />
          </button>
        </>
      }
      note="Indian benchmarks are the NSE/BSE indices themselves. US markets are shown through liquid ETFs as proxies: large cap, Nasdaq-100, small cap, long Treasuries and gold. Bars compare each day's move within this list."
    >
      {loading && !data && (
        <div className="p-4">
          <LoadingBlock rows={6} />
        </div>
      )}
      {error ? (
        <div className="p-4">
          <ErrorNotice error={error} onRetry={reload} />
        </div>
      ) : null}
      {data && (
        <div className="grid divide-line lg:grid-cols-2 lg:divide-x">
          <MarketGroup title="India" results={data.filter((r) => INDIA.includes(r.symbol))} />
          <MarketGroup title="United States" results={data.filter((r) => US.includes(r.symbol))} />
        </div>
      )}
    </Block>
  );
}

function WatchlistPanel() {
  const { user, status } = useAuth();
  const [actionError, setActionError] = useState<string | null>(null);
  const { data, error, loading, reload, setData } = useAsync<QuoteResult[]>(
    user
      ? async () => {
          const items = await api.watchlist();
          return items.length ? api.quotes(items.map((i) => i.symbol)) : [];
        }
      : null,
    [user?.id],
  );

  async function add(symbol: string) {
    setActionError(null);
    try {
      await api.watch(symbol);
      reload();
    } catch (err) {
      setActionError(describeError(err));
    }
  }

  async function remove(symbol: string) {
    setActionError(null);
    const previous = data;
    setData((data ?? []).filter((r) => r.symbol !== symbol));
    try {
      await api.unwatch(symbol);
    } catch (err) {
      setData(previous);
      setActionError(describeError(err));
    }
  }

  return (
    <Block title="Watchlist" actions={data && data.length > 0 ? <span className="text-xs text-ink-faint">{data.length} symbols</span> : undefined}>
      {status === 'loading' && (
        <div className="p-4">
          <LoadingBlock rows={3} />
        </div>
      )}
      {(status === 'anonymous' || status === 'unreachable') && (
        <EmptyState icon={<Star className="h-6 w-6" />} title="Keep a watchlist" action={<Link href="/login" className="btn-primary text-xs">Sign in</Link>}>
          Signed-in users can save symbols, portfolios, research reports and documents.
        </EmptyState>
      )}
      {user && (
        <>
          <div className="px-4 py-2">
            <SymbolSearch placeholder="Add a symbol, e.g. RELIANCE.NS or AAPL" onSelect={(s) => add(s)} />
            {actionError && <p className="mt-2 text-xs text-down">{actionError}</p>}
          </div>
          {loading && !data && (
            <div className="p-4">
              <LoadingBlock rows={3} />
            </div>
          )}
          {error ? (
            <div className="p-4">
              <ErrorNotice error={error} onRetry={reload} />
            </div>
          ) : null}
          {data && data.length === 0 && <EmptyState title="Your watchlist is empty">Search above to add a symbol.</EmptyState>}
          {data && data.length > 0 && <QuoteTable results={data} onRemove={remove} labels={LABELS} />}
        </>
      )}
    </Block>
  );
}

function RecentResearch() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useAsync<{ items: ResearchSummary[] }>(user ? () => api.researchHistory(undefined, 6) : null, [user?.id]);
  if (!user) return null;
  return (
    <Block
      title="Recent research"
      actions={
        <Link href="/research" className="text-xs text-ink-muted hover:text-accent">
          View all
        </Link>
      }
    >
      {loading && (
        <div className="p-4">
          <LoadingBlock rows={3} />
        </div>
      )}
      {error ? (
        <div className="p-4">
          <ErrorNotice error={error} onRetry={reload} />
        </div>
      ) : null}
      {data && data.items.length === 0 && (
        <EmptyState title="No saved reports yet" action={<Link href="/research" className="btn-ghost text-xs">Run research</Link>}>
          Reports you generate while signed in are saved here.
        </EmptyState>
      )}
      {data && data.items.length > 0 && (
        <ul className="pb-1">
          {data.items.map((r) => (
            <li key={r.id} className="border-t border-line/70 first:border-t-0">
              <Link href={`/research?id=${r.id}`} className="flex items-baseline gap-3 px-4 py-2 hover:bg-raised/40">
                <span className="w-24 shrink-0 truncate text-[13px] font-medium text-ink">{r.symbol}</span>
                <span className="min-w-0 flex-1 truncate text-[13px] text-ink-muted">{r.question || r.name || 'Research report'}</span>
                <span className="shrink-0 text-2xs text-ink-faint">{relativeTime(r.created_at)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Block>
  );
}

const WORKFLOWS = [
  { href: '/asset', icon: LineChart, title: 'Analyze an asset', text: 'Candles, indicators, return and risk, drawdowns, benchmark comparison.' },
  { href: '/portfolio', icon: PieChart, title: 'Build a portfolio', text: 'Weights, risk contribution, correlation and historical stress episodes.' },
  { href: '/research', icon: BrainCircuit, title: 'Generate research', text: 'A report where every claim cites computed metrics, news or filings.' },
  { href: '/documents', icon: FileText, title: 'Index documents', text: 'Upload filings and transcripts and use them as cited evidence.' },
];

function Workflows() {
  return (
    <Block title="Workflows">
      <ul className="pb-1">
        {WORKFLOWS.map(({ href, icon: Icon, title, text }) => (
          <li key={href} className="border-t border-line/70 first:border-t-0">
            <Link href={href} className="group flex items-start gap-3 px-4 py-2.5 hover:bg-raised/40">
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-ink-faint group-hover:text-accent" aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block text-[13px] font-medium text-ink group-hover:text-accent">{title}</span>
                <span className="block text-xs leading-relaxed text-ink-faint">{text}</span>
              </span>
              <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-faint opacity-0 transition-opacity group-hover:opacity-100" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </Block>
  );
}

function SystemPanel() {
  const { status, reachable, reload } = useSystem();
  if (reachable === false)
    return (
      <Block title="Backend">
        <div className="p-4">
          <ErrorNotice error={new Error('The ARGUS backend is not reachable. Start it, or set its URL in Settings.')} onRetry={reload} />
        </div>
      </Block>
    );
  if (!status) return null;
  const r = status.research;
  const model =
    r.mode !== 'llm'
      ? 'Deterministic (no language model)'
      : r.llm_local === false
        ? `${r.llm_model} via ${r.llm_host ?? 'remote API'}`
        : `Local model: ${r.llm_model}`;
  const rows: { label: string; value: string; note?: string }[] = [
    { label: 'Market data', value: status.market_data.provider, note: status.market_data.note },
    {
      label: 'Research synthesis',
      value: model,
      note:
        r.mode === 'llm'
          ? `${r.llm_local === false ? 'Questions and evidence are sent to this hosted API. ' : ''}Model output is validated: every claim must cite evidence and every number must match it.`
          : 'Reports are assembled from cited evidence by rule-based agents.',
    },
    { label: 'Embeddings', value: `${status.embeddings.provider}${status.embeddings.ready ? '' : ` (${status.embeddings.status})`}` },
    { label: 'SEC EDGAR', value: status.sec_edgar ? 'Enabled' : 'Not configured' },
  ];
  return (
    <Block title="System">
      <dl className="pb-1">
        {rows.map((row) => (
          <div key={row.label} className="border-t border-line/70 px-4 py-2 first:border-t-0">
            <dt className="text-xs text-ink-faint">{row.label}</dt>
            <dd className="text-[13px] text-ink">{row.value}</dd>
            {row.note && <dd className="mt-0.5 text-2xs leading-relaxed text-ink-faint">{row.note}</dd>}
          </div>
        ))}
      </dl>
    </Block>
  );
}

export default function OverviewPage() {
  const { user } = useAuth();
  return (
    <div className="space-y-5">
      <div>
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{user ? `Welcome back${user.display_name ? `, ${user.display_name}` : ''}` : 'Research terminal'}</h1>
          <p className="mt-1 text-[13px] text-ink-muted">Evidence before conclusions: deterministic metrics, sourced data, cited research.</p>
        </div>
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-4">
          <MarketPanel />
          <WatchlistPanel />
        </div>
        <div className="min-w-0 space-y-4">
          <Workflows />
          <RecentResearch />
          <SystemPanel />
        </div>
      </div>
    </div>
  );
}
