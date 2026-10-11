'use client';

import { Suspense, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { BrainCircuit, CheckCircle2, Circle, Loader2, Square, Trash2, XCircle } from 'lucide-react';
import { api, ApiError, streamResearch } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useSystem } from '@/lib/system';
import { useAsync } from '@/lib/useAsync';
import { normalizeSymbol, relativeTime } from '@/lib/format';
import type { ResearchReport, ResearchStep } from '@/lib/types';
import ReportView from '@/components/research/ReportView';
import { EmptyState, ErrorNotice, LoadingBlock, PageHeader, Panel, SegmentedControl } from '@/components/ui';

const STAGES: { key: string; label: string }[] = [
  { key: 'market_data', label: 'Market data & quant engine' },
  { key: 'documents', label: 'Document retrieval' },
  { key: 'evidence', label: 'Evidence ledger' },
  { key: 'agents', label: 'Specialist agents' },
  { key: 'synthesis', label: 'Synthesis & validation' },
  { key: 'report', label: 'Report' },
];
const PERIODS = [
  { value: '6mo', label: '6M' },
  { value: '1y', label: '1Y' },
  { value: '3y', label: '3Y' },
  { value: '5y', label: '5Y' },
] as const;
type ResearchPeriod = (typeof PERIODS)[number]['value'];

function Progress({ steps }: { steps: Record<string, ResearchStep> }) {
  return (
    <ol className="space-y-1.5" aria-live="polite">
      {STAGES.map((stage) => {
        const step = steps[stage.key];
        const Icon = !step ? Circle : step.status === 'running' ? Loader2 : step.status === 'failed' ? XCircle : CheckCircle2;
        const color = !step ? 'text-ink-faint' : step.status === 'running' ? 'text-accent animate-spin' : step.status === 'failed' ? 'text-down' : step.status === 'ok' ? 'text-up' : 'text-warn';
        return (
          <li key={stage.key} className="flex items-start gap-2 text-sm">
            <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${color}`} aria-hidden />
            <span className={step ? 'text-ink' : 'text-ink-faint'}>{stage.label}</span>
            {step?.detail && <span className="ml-auto truncate pl-2 text-2xs text-ink-faint" title={step.detail}>{step.detail}</span>}
          </li>
        );
      })}
    </ol>
  );
}

function History({ activeId, refreshKey, onDeleted }: { activeId: string | null; refreshKey: number; onDeleted: (id: string) => void }) {
  const { user } = useAuth();
  const { data, error, loading, reload, setData } = useAsync(user ? () => api.researchHistory(undefined, 50) : null, [user?.id, refreshKey]);
  if (!user)
    return (
      <Panel title="History">
        <p className="text-sm text-ink-muted">
          <Link href="/login" className="text-accent hover:underline">
            Sign in
          </Link>{' '}
          to save reports and include your own documents as evidence.
        </p>
      </Panel>
    );
  async function remove(id: string) {
    if (!window.confirm('Delete this saved report?')) return;
    try {
      await api.deleteResearch(id);
      setData(data ? { ...data, items: data.items.filter((i) => i.id !== id) } : data);
      onDeleted(id);
    } catch {
      reload();
    }
  }
  return (
    <Panel title="History" bodyClassName="p-0">
      {loading && <div className="p-4"><LoadingBlock rows={4} /></div>}
      {error ? <div className="p-4"><ErrorNotice error={error} onRetry={reload} compact /></div> : null}
      {data && data.items.length === 0 && <EmptyState title="No saved reports" />}
      {data && data.items.length > 0 && (
        <ul className="max-h-[28rem] divide-y divide-line overflow-auto">
          {data.items.map((r) => (
            <li key={r.id} className={`group flex items-center ${r.id === activeId ? 'bg-accent/10' : ''}`}>
              <Link href={`/research?id=${r.id}`} className="min-w-0 flex-1 px-4 py-2 hover:bg-raised/50">
                <span className="flex items-center gap-2">
                  <span className="num text-sm font-semibold text-accent">{r.symbol}</span>
                  <span className="text-2xs text-ink-faint">{relativeTime(r.created_at)}</span>
                </span>
                <span className="block truncate text-xs text-ink-muted">{r.question || `${r.claims} claims · ${r.generation_mode}`}</span>
              </Link>
              <button type="button" aria-label="Delete report" onClick={() => remove(r.id)} className="mr-2 rounded p-1 text-ink-faint opacity-0 hover:text-down focus:opacity-100 group-hover:opacity-100">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function ResearchPageInner() {
  const params = useSearchParams();
  const router = useRouter();
  const { user } = useAuth();
  const { status } = useSystem();
  const reportId = params.get('id');
  const [symbol, setSymbol] = useState(params.get('symbol')?.toUpperCase() ?? '');
  const [question, setQuestion] = useState('');
  const [period, setPeriod] = useState<ResearchPeriod>('1y');
  const [steps, setSteps] = useState<Record<string, ResearchStep>>({});
  const [running, setRunning] = useState(false);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  const saved = useAsync<ResearchReport>(reportId && user ? () => api.researchReport(reportId) : null, [reportId, user?.id]);
  useEffect(() => {
    if (saved.data) setReport(saved.data);
  }, [saved.data]);
  useEffect(() => () => abortRef.current?.abort(), []);

  const normalized = normalizeSymbol(symbol);

  async function run(event: React.FormEvent) {
    event.preventDefault();
    if (!normalized || running) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setRunning(true);
    setError(null);
    setReport(null);
    setSteps({});
    try {
      const result = await streamResearch(
        { symbol: normalized, question: question.trim() || undefined, period, save: true },
        { signal: controller.signal, onStep: (step) => setSteps((s) => ({ ...s, [step.step]: step })) },
      );
      setReport(result);
      if (result.id) {
        router.replace(`/research?id=${result.id}`, { scroll: false });
        setRefreshKey((k) => k + 1);
      }
    } catch (err) {
      if (!(err instanceof ApiError && err.code === 'cancelled')) setError(err);
    } finally {
      setRunning(false);
    }
  }

  const deterministic = status?.research.mode !== 'llm';

  return (
    <div className="space-y-5">
      <PageHeader
        title="Research"
        subtitle="Specialist agents assemble a report in which every claim cites a computed metric, a sourced quote, a headline, or a passage from your documents."
      />
      <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-4">
          <Panel title="New report">
            <form onSubmit={run} className="space-y-3">
              <div>
                <label className="label" htmlFor="r-symbol">
                  Symbol
                </label>
                <input id="r-symbol" className="input num uppercase" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="NVDA" required />
                {symbol && !normalized && <p className="mt-1 text-2xs text-down">Not a valid symbol.</p>}
              </div>
              <div>
                <label className="label" htmlFor="r-question">
                  Question <span className="text-ink-faint">(optional)</span>
                </label>
                <textarea
                  id="r-question"
                  className="input min-h-[80px] resize-y"
                  maxLength={500}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="e.g. What are the main risks, and what do my documents say about margins?"
                />
                <p className="mt-0.5 text-right text-2xs text-ink-faint">{question.length}/500</p>
              </div>
              <div>
                <span className="label">Quantitative window</span>
                <SegmentedControl label="Window" size="xs" options={PERIODS} value={period} onChange={setPeriod} />
              </div>
              {running ? (
                <button type="button" className="btn-ghost w-full" onClick={() => abortRef.current?.abort()}>
                  <Square className="h-3.5 w-3.5" aria-hidden /> Cancel
                </button>
              ) : (
                <button type="submit" className="btn-primary w-full" disabled={!normalized}>
                  <BrainCircuit className="h-4 w-4" aria-hidden /> Generate report
                </button>
              )}
              <p className="text-2xs leading-relaxed text-ink-faint">
                {deterministic
                  ? 'No language model is configured: rule-based agents assemble the report and questions are answered with the most relevant evidence.'
                  : `Synthesis uses ${status?.research.llm_model}${
                      status?.research.llm_local === false ? ` via ${status.research.llm_host ?? 'a hosted API'} (your question and the evidence are sent there)` : ''
                    }; its claims are validated against the evidence before display.`}
                {!user && ' Signed-out reports are not saved and cannot use documents.'}
              </p>
            </form>
          </Panel>
          {(running || Object.keys(steps).length > 0) && (
            <Panel title="Progress">
              <Progress steps={steps} />
            </Panel>
          )}
          <History
            activeId={reportId}
            refreshKey={refreshKey}
            onDeleted={(id) => {
              if (id === reportId) {
                setReport(null);
                router.replace('/research');
              }
            }}
          />
        </div>
        <div className="min-w-0">
          {error ? <ErrorNotice error={error} /> : null}
          {saved.error && !report ? <ErrorNotice error={saved.error} onRetry={saved.reload} /> : null}
          {saved.loading && !report && <Panel><LoadingBlock rows={8} label="Loading saved report" /></Panel>}
          {report && <ReportView report={report} />}
          {!report && !running && !error && !saved.loading && !saved.error && (
            <Panel>
              <EmptyState icon={<BrainCircuit className="h-7 w-7" />} title="Generate an evidence-grounded report">
                Enter a symbol and optionally a question. Click any <span className="num text-accent">[M3]</span>-style citation to inspect the
                underlying metric, quote, headline or document passage.
              </EmptyState>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ResearchPage() {
  return (
    <Suspense fallback={null}>
      <ResearchPageInner />
    </Suspense>
  );
}
