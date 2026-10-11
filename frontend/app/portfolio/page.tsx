'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { FolderOpen, Play, Save, Trash2 } from 'lucide-react';
import { api, describeError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useAsync } from '@/lib/useAsync';
import { normalizeSymbol, PERIODS, relativeTime, type Period } from '@/lib/format';
import type { HoldingInput, PortfolioAnalysis, RebalancingModel, SavedPortfolio } from '@/lib/types';
import HoldingsEditor from '@/components/portfolio/HoldingsEditor';
import { type DraftHolding, validateHoldings } from '@/lib/holdings';
import PortfolioResults from '@/components/portfolio/PortfolioResults';
import { EmptyState, ErrorNotice, LoadingBlock, PageHeader, Panel, SegmentedControl } from '@/components/ui';

const DRAFT_KEY = 'argus_portfolio_draft';
const DEFAULT_ROWS: DraftHolding[] = [
  { id: 1, symbol: 'SPY', weight: '50' },
  { id: 2, symbol: 'TLT', weight: '30' },
  { id: 3, symbol: 'GLD', weight: '20' },
];
const MODELS = [
  { value: 'daily_rebalanced', label: 'Daily rebalanced' },
  { value: 'buy_and_hold', label: 'Buy & hold' },
] as const;
const PERIOD_OPTIONS = PERIODS.filter((p) => p !== '1mo').map((p) => ({ value: p, label: p.toUpperCase() }));

interface Draft {
  rows: DraftHolding[];
  model: RebalancingModel;
  benchmark: string;
  period: Period;
}

function toHoldings(rows: DraftHolding[]): HoldingInput[] {
  return rows.map((r) => ({ symbol: normalizeSymbol(r.symbol) ?? r.symbol, weight: Number(r.weight) }));
}

function fromHoldings(holdings: HoldingInput[]): DraftHolding[] {
  return holdings.map((h, i) => ({ id: i + 1, symbol: h.symbol, weight: String(+h.weight.toFixed(4)) }));
}

function SavedPortfolios({
  activeId,
  onLoad,
  refreshKey,
}: {
  activeId: string | null;
  onLoad: (p: SavedPortfolio) => void;
  refreshKey: number;
}) {
  const { user, status } = useAuth();
  const { data, error, loading, reload } = useAsync(user ? () => api.listPortfolios() : null, [user?.id, refreshKey]);
  if (status === 'anonymous' || status === 'unreachable')
    return (
      <Panel title="Saved portfolios">
        <p className="text-sm text-ink-muted">
          <Link href="/login" className="text-accent hover:underline">
            Sign in
          </Link>{' '}
          to save and reload portfolios. Analysis works without an account.
        </p>
      </Panel>
    );
  return (
    <Panel title="Saved portfolios" bodyClassName="p-0">
      {loading && <div className="p-4"><LoadingBlock rows={3} /></div>}
      {error ? <div className="p-4"><ErrorNotice error={error} onRetry={reload} compact /></div> : null}
      {data && data.items.length === 0 && <EmptyState icon={<FolderOpen className="h-5 w-5" />} title="None saved yet" />}
      {data && data.items.length > 0 && (
        <ul className="max-h-72 divide-y divide-line overflow-auto">
          {data.items.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => onLoad(p)}
                className={`flex w-full items-center gap-2 px-4 py-2 text-left hover:bg-raised/60 ${p.id === activeId ? 'bg-accent/10' : ''}`}
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm text-ink">{p.name}</span>
                  <span className="num block truncate text-2xs text-ink-faint">{p.holdings.map((h) => h.symbol).join(' · ')}</span>
                </span>
                <span className="text-2xs text-ink-faint">{relativeTime(p.updated_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function PortfolioPageInner() {
  const params = useSearchParams();
  const { user } = useAuth();
  // benchmark '' = automatic (the backend picks SPY, or ^NSEI when every holding is an NSE/BSE listing).
  const [draft, setDraft] = useState<Draft>({ rows: DEFAULT_ROWS, model: 'daily_rebalanced', benchmark: '', period: '3y' });
  const [hydrated, setHydrated] = useState(false);
  const [analysis, setAnalysis] = useState<{ result: PortfolioAnalysis; holdings: HoldingInput[] } | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState<{ id: string; version: number; name: string } | null>(null);
  const [name, setName] = useState('');
  const [saveState, setSaveState] = useState<{ busy: boolean; message: string | null; error: string | null }>({ busy: false, message: null, error: null });
  const [refreshKey, setRefreshKey] = useState(0);

  // Restore the unsaved draft (per-browser convenience), then apply ?add=SYMBOL.
  useEffect(() => {
    let next = draft;
    try {
      const raw = window.localStorage.getItem(DRAFT_KEY);
      if (raw) next = { ...draft, ...JSON.parse(raw) };
      // Drafts saved before automatic benchmarks always stored 'SPY'; treat that as automatic.
      if (next.benchmark === 'SPY') next = { ...next, benchmark: '' };
    } catch {
      // ignore unreadable drafts
    }
    const add = normalizeSymbol(params.get('add') ?? '');
    if (add && !next.rows.some((r) => normalizeSymbol(r.symbol) === add)) {
      next = { ...next, rows: [...next.rows, { id: Math.max(0, ...next.rows.map((r) => r.id)) + 1, symbol: add, weight: '' }] };
    }
    setDraft(next);
    setHydrated(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    } catch {
      // storage unavailable
    }
  }, [draft, hydrated]);

  const validation = useMemo(() => validateHoldings(draft.rows), [draft.rows]);
  const benchmarkOk = draft.benchmark.trim() === '' || normalizeSymbol(draft.benchmark) !== null;
  const chosenBenchmark = draft.benchmark.trim() ? normalizeSymbol(draft.benchmark) ?? undefined : undefined;
  const analysisMatchesDraft =
    analysis !== null &&
    analysis.holdings.map((h) => h.symbol).join(',') === toHoldings(draft.rows).map((h) => h.symbol).join(',');

  async function analyze() {
    if (!validation.valid || !benchmarkOk) return;
    setRunning(true);
    setError(null);
    const holdings = toHoldings(draft.rows);
    try {
      const result = await api.analyzePortfolio({ holdings, model: draft.model, benchmark: chosenBenchmark, period: draft.period });
      setAnalysis({ result, holdings });
    } catch (err) {
      setError(err);
    } finally {
      setRunning(false);
    }
  }

  function load(p: SavedPortfolio) {
    setDraft({ rows: fromHoldings(p.holdings), model: p.rebalancing, benchmark: p.benchmark, period: draft.period });
    setSaved({ id: p.id, version: p.version, name: p.name });
    setName(p.name);
    setAnalysis(null);
    setSaveState({ busy: false, message: `Loaded "${p.name}".`, error: null });
  }

  async function save(asNew: boolean) {
    if (!validation.valid || !name.trim()) return;
    setSaveState({ busy: true, message: null, error: null });
    const body = {
      name: name.trim(),
      description: null,
      // Save the benchmark actually used: the user's choice, else the one the last analysis resolved.
      benchmark: chosenBenchmark ?? (analysisMatchesDraft ? analysis?.result.benchmark : undefined) ?? 'SPY',
      rebalancing: draft.model,
      holdings: toHoldings(draft.rows),
    };
    try {
      const result =
        saved && !asNew ? await api.updatePortfolio(saved.id, { ...body, version: saved.version }) : await api.createPortfolio(body);
      setSaved({ id: result.id, version: result.version, name: result.name });
      setSaveState({ busy: false, message: `Saved "${result.name}".`, error: null });
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setSaveState({ busy: false, message: null, error: describeError(err) });
    }
  }

  async function remove() {
    if (!saved || !window.confirm(`Delete "${saved.name}"? This cannot be undone.`)) return;
    try {
      await api.deletePortfolio(saved.id);
      setSaved(null);
      setSaveState({ busy: false, message: 'Portfolio deleted.', error: null });
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setSaveState({ busy: false, message: null, error: describeError(err) });
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Portfolio lab"
        subtitle="Historical analysis of a fixed allocation under an explicit rebalancing model. Backward-looking; not a forecast or recommendation."
      />
      <div className="grid gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
        <div className="space-y-4">
          <Panel title={saved ? `Editing: ${saved.name}` : 'Allocation'}>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void analyze();
              }}
              className="space-y-4"
            >
              <HoldingsEditor rows={draft.rows} onChange={(rows) => setDraft({ ...draft, rows })} validation={validation} />
              <div>
                <span className="label">Rebalancing model</span>
                <SegmentedControl label="Rebalancing model" options={MODELS} value={draft.model} onChange={(model) => setDraft({ ...draft, model })} />
              </div>
              <div>
                <span className="label">Window</span>
                <SegmentedControl label="Analysis window" size="xs" options={PERIOD_OPTIONS} value={draft.period} onChange={(period) => setDraft({ ...draft, period })} />
              </div>
              <div className="w-32">
                <label className="label" htmlFor="pf-bench">
                  Benchmark
                </label>
                <input
                  id="pf-bench"
                  className={`input num uppercase placeholder:normal-case ${benchmarkOk ? '' : 'border-down'}`}
                  value={draft.benchmark}
                  placeholder={analysis && !draft.benchmark ? `Auto: ${analysis.result.benchmark}` : 'Auto'}
                  title="Leave empty to use the market's index (SPY; ^NSEI when every holding is an NSE/BSE listing)"
                  onChange={(e) => setDraft({ ...draft, benchmark: e.target.value.toUpperCase() })}
                />
              </div>
              {validation.errors.length > 0 && <ul className="space-y-0.5 text-xs text-warn">{validation.errors.map((e) => <li key={e}>{e}</li>)}</ul>}
              <button type="submit" className="btn-primary w-full" disabled={!validation.valid || !benchmarkOk || running}>
                <Play className="h-4 w-4" aria-hidden /> {running ? 'Analyzing…' : 'Analyze portfolio'}
              </button>
            </form>
          </Panel>

          {user && (
            <Panel title="Save">
              <div className="space-y-2">
                <label className="label" htmlFor="pf-name">
                  Name
                </label>
                <input id="pf-name" className="input" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. 60/40 core" />
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="btn-ghost text-xs" disabled={!validation.valid || !name.trim() || saveState.busy} onClick={() => save(false)}>
                    <Save className="h-3.5 w-3.5" aria-hidden /> {saved ? 'Update' : 'Save'}
                  </button>
                  {saved && (
                    <>
                      <button type="button" className="btn-ghost text-xs" disabled={!validation.valid || !name.trim() || saveState.busy} onClick={() => save(true)}>
                        Save as new
                      </button>
                      <button type="button" className="btn-danger ml-auto text-xs" onClick={remove}>
                        <Trash2 className="h-3.5 w-3.5" aria-hidden /> Delete
                      </button>
                    </>
                  )}
                </div>
                {saveState.message && <p className="text-xs text-up">{saveState.message}</p>}
                {saveState.error && (
                  <p className="text-xs text-down">{saveState.error}</p>
                )}
              </div>
            </Panel>
          )}
          <SavedPortfolios activeId={saved?.id ?? null} onLoad={load} refreshKey={refreshKey} />
        </div>

        <div className="min-w-0 space-y-4">
          {error ? <ErrorNotice error={error} onRetry={analyze} /> : null}
          {running && !analysis && (
            <Panel>
              <LoadingBlock rows={8} label="Fetching histories and computing analytics" />
            </Panel>
          )}
          {analysis && (
            <div className={running ? 'opacity-60' : ''}>
              <PortfolioResults analysis={analysis.result} holdings={analysis.holdings} />
            </div>
          )}
          {!analysis && !running && !error && (
            <Panel>
              <EmptyState title="Define an allocation and run the analysis">
                Weights are percentages that must sum to 100. Daily-rebalanced portfolios reset to target weights every day; buy-and-hold
                portfolios let winners grow. The two models produce different results on purpose.
              </EmptyState>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}

export default function PortfolioPage() {
  return (
    <Suspense fallback={null}>
      <PortfolioPageInner />
    </Suspense>
  );
}
