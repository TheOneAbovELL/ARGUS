'use client';

import { useMemo, useState } from 'react';
import { CheckCircle2, Download, ExternalLink, FileText, ShieldCheck, TriangleAlert } from 'lucide-react';
import { api } from '@/lib/api';
import { dateTime, shortDate } from '@/lib/format';
import type { Claim, EvidenceItem, ReportSection, ResearchReport } from '@/lib/types';
import { Notes, Panel } from '@/components/ui';
import { claimBadge } from '@/lib/claims';

const KIND_LABEL: Record<EvidenceItem['kind'], string> = {
  quote: 'Quote',
  profile: 'Profile',
  metric: 'Computed metric',
  news: 'News',
  document: 'Document passage',
  method: 'Methodology',
};

const SCENARIO_TONE: Record<string, string> = {
  bull: 'border-up/40',
  base: 'border-info/40',
  bear: 'border-down/40',
};

function EvidenceChip({ id, evidence, onSelect, active }: { id: string; evidence?: EvidenceItem; onSelect: (id: string) => void; active: boolean }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(id)}
      title={evidence ? `${evidence.label}: ${evidence.statement}` : 'Evidence not found'}
      className={`num mx-0.5 inline-flex rounded border px-1 align-baseline text-[10px] font-semibold leading-4 transition-colors ${
        active ? 'border-accent bg-accent text-bg' : evidence ? 'border-accent/40 text-accent hover:bg-accent/10' : 'border-down/50 text-down'
      }`}
    >
      {id}
    </button>
  );
}

function ClaimLine({
  claim,
  evidence,
  selected,
  onSelect,
  showOrigin,
}: {
  claim: Claim;
  evidence: Map<string, EvidenceItem>;
  selected: string | null;
  onSelect: (id: string) => void;
  showOrigin: boolean;
}) {
  const interpretation = claim.kind === 'interpretation';
  const badge = claimBadge(claim, evidence);
  return (
    <li className="flex gap-2 text-sm leading-relaxed">
      <span
        className={`mt-1 h-fit shrink-0 rounded px-1 text-2xs font-medium ${
          interpretation ? 'bg-info/10 text-info' : 'bg-raised text-ink-muted'
        }`}
        title={badge.title}
      >
        {badge.label}
      </span>
      <span className={interpretation ? 'italic text-ink-muted' : 'text-ink'}>
        {claim.text}
        {claim.evidence_ids.map((id) => (
          <EvidenceChip key={id} id={id} evidence={evidence.get(id)} active={selected === id} onSelect={onSelect} />
        ))}
        {showOrigin && claim.origin === 'agent' && (
          <span className="ml-1 rounded border border-line px-1 align-baseline text-[10px] not-italic text-ink-faint" title="Written by ARGUS's rule-based agents, not the language model">
            rule-based
          </span>
        )}
      </span>
    </li>
  );
}

function SectionBlock({
  section,
  evidence,
  selected,
  onSelect,
  showOrigin = false,
}: {
  section: ReportSection;
  evidence: Map<string, EvidenceItem>;
  selected: string | null;
  onSelect: (id: string) => void;
  showOrigin?: boolean;
}) {
  if (!section.claims.length) return null;
  return (
    <section>
      <h3 className="mb-2 text-sm font-semibold text-ink">{section.title}</h3>
      <ul className="space-y-2">
        {section.claims.map((claim, i) => (
          <ClaimLine key={i} claim={claim} evidence={evidence} selected={selected} onSelect={onSelect} showOrigin={showOrigin} />
        ))}
      </ul>
    </section>
  );
}

function EvidenceCard({ item, active }: { item: EvidenceItem; active: boolean }) {
  return (
    <li id={`evidence-${item.id}`} className={`rounded border px-3 py-2 transition-colors ${active ? 'border-accent bg-accent/5' : 'border-line'}`}>
      <div className="flex items-center gap-2">
        <span className="num text-xs font-bold text-accent">{item.id}</span>
        <span className="text-2xs text-ink-faint">{KIND_LABEL[item.kind] ?? item.kind}</span>
        {item.untrusted && (
          <span className="chip ml-auto border-warn/40 text-warn" title="Third-party text. Quoted as data; never treated as instructions.">
            third-party
          </span>
        )}
      </div>
      <p className="mt-1 text-xs font-medium text-ink">{item.label}</p>
      <p className={`mt-0.5 text-xs leading-relaxed ${item.kind === 'document' ? 'border-l-2 border-line pl-2 text-ink-muted' : 'text-ink-muted'}`}>{item.statement}</p>
      <p className="mt-1 flex flex-wrap items-center gap-x-2 text-2xs text-ink-faint">
        <span>{item.source}</span>
        {item.as_of && <span>· {item.as_of.length > 10 ? dateTime(item.as_of) : shortDate(item.as_of)}</span>}
        {item.retrieval_score !== null && <span className="num">· relevance {item.retrieval_score.toFixed(2)}</span>}
        {item.url && /^https?:\/\//.test(item.url) && (
          <a href={item.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 text-accent hover:underline">
            source <ExternalLink className="h-3 w-3" aria-hidden />
          </a>
        )}
        {item.document_id && (
          <a href={api.documentFileUrl(item.document_id, item.page_number)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 text-accent hover:underline">
            <FileText className="h-3 w-3" aria-hidden /> open page {item.page_number}
          </a>
        )}
      </p>
    </li>
  );
}

function downloadJson(report: ResearchReport) {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `argus-research-${report.symbol}-${report.generated_at.slice(0, 10)}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function ReportView({ report }: { report: ResearchReport }) {
  const [selected, setSelected] = useState<string | null>(null);
  const evidence = useMemo(() => new Map(report.evidence.map((e) => [e.id, e])), [report.evidence]);
  const v = report.generation.validation;
  const llm = report.generation.mode === 'llm';
  const backfilled = v.claims_backfilled ?? 0;
  const select = (id: string) => {
    setSelected(id);
    document.getElementById(`evidence-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };
  // When the user asked a question, lead with the answer.
  const sections = useMemo(
    () => [...report.sections].sort((a, b) => Number(b.key === 'answer') - Number(a.key === 'answer')),
    [report.sections],
  );
  const grouped = useMemo(() => {
    const order: EvidenceItem['kind'][] = ['metric', 'quote', 'profile', 'news', 'document', 'method'];
    return order.map((kind) => ({ kind, items: report.evidence.filter((e) => e.kind === kind) })).filter((g) => g.items.length);
  }, [report.evidence]);

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_400px]">
      <div className="min-w-0 space-y-4">
        <Panel bodyClassName="p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-ink">
                <span className="num text-accent">{report.symbol}</span> {report.name && <span className="text-ink-muted">· {report.name}</span>}
              </h2>
              {report.question && <p className="mt-1 text-sm text-ink">“{report.question}”</p>}
              <p className="mt-1 text-2xs text-ink-faint">
                Generated {dateTime(report.generated_at)}
                {report.window.start && ` · window ${shortDate(report.window.start)} – ${shortDate(report.window.end)}`}
                {report.window.benchmark && ` · benchmark ${report.window.benchmark}`}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`chip ${report.generation.mode === 'llm' ? 'border-info/40 bg-info/10 text-info' : 'border-line bg-raised text-ink-muted'}`}
                title={report.generation.fallback_reason ?? undefined}
              >
                {report.generation.mode === 'llm' ? `Synthesized by ${report.generation.model}` : 'Deterministic agents'}
              </span>
              <span className="chip border-up/40 bg-up/10 text-up" title="Claims that passed citation and number checks">
                <ShieldCheck className="h-3 w-3" aria-hidden /> {v.claims_accepted}/{v.claims_total}{' '}
                {llm ? 'model claims verified' : 'claims verified'}
              </span>
              <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={() => downloadJson(report)}>
                <Download className="h-3.5 w-3.5" aria-hidden /> JSON
              </button>
            </div>
          </div>
          {llm && backfilled > 0 && (
            <p className="mt-2 text-xs text-ink-muted">
              {backfilled} rule-based claim{backfilled === 1 ? '' : 's'} fill sections the model left without valid claims (marked
              &ldquo;rule-based&rdquo;).
            </p>
          )}
          {report.generation.fallback_reason && (
            <p className="mt-2 text-xs text-warn">Fell back to deterministic synthesis: {report.generation.fallback_reason}</p>
          )}
        </Panel>

        <Panel bodyClassName="space-y-5 p-4">
          {sections.map((section) => (
            <SectionBlock key={section.key} section={section} evidence={evidence} selected={selected} onSelect={select} showOrigin={llm} />
          ))}
        </Panel>

        {report.scenarios.some((s) => s.claims.length) && (
          <div className="grid gap-3 md:grid-cols-3">
            {report.scenarios.map((s) => (
              <div key={s.key} className={`panel border-t-2 p-4 ${SCENARIO_TONE[s.key] ?? ''}`}>
                <SectionBlock section={s} evidence={evidence} selected={selected} onSelect={select} showOrigin={llm} />
              </div>
            ))}
          </div>
        )}
        <p className="text-2xs text-ink-faint">Scenarios are hypotheses framed from the evidence, not forecasts or recommendations.</p>

        {report.limitations.length > 0 && <Notes title="Limitations" items={report.limitations} />}

        {v.rejected.length > 0 && (
          <Panel title={`Rejected claims (${v.rejected.length})`}>
            <p className="mb-2 text-xs text-ink-muted">These model-proposed claims failed validation and were removed from the report.</p>
            <ul className="space-y-2">
              {v.rejected.map((r, i) => (
                <li key={i} className="rounded border border-down/30 px-3 py-2 text-xs">
                  <p className="text-ink-muted line-through decoration-down/60">{r.text}</p>
                  <p className="mt-1 text-down">
                    <TriangleAlert className="mr-1 inline h-3 w-3" aria-hidden />
                    {r.reasons.join('; ')}
                  </p>
                </li>
              ))}
            </ul>
          </Panel>
        )}

        <Panel title="Execution trace">
          <ol className="space-y-1 text-xs">
            {report.trace.map((step, i) => (
              <li key={i} className="flex items-center gap-2">
                <CheckCircle2 className={`h-3.5 w-3.5 ${step.status === 'ok' ? 'text-up' : step.status === 'failed' ? 'text-down' : 'text-warn'}`} aria-hidden />
                <span className="num w-28 text-ink">{step.step}</span>
                <span className="w-16 text-ink-muted">{step.status}</span>
                <span className="num w-20 text-right text-ink-faint">{step.duration_ms.toFixed(0)} ms</span>
                {step.detail && <span className="min-w-0 truncate text-ink-faint" title={step.detail}>{step.detail}</span>}
              </li>
            ))}
          </ol>
        </Panel>
        <p className="text-2xs text-ink-faint">{report.disclaimer}</p>
      </div>

      <aside className="xl:sticky xl:top-16 xl:max-h-[calc(100vh-5rem)] xl:overflow-auto" aria-label="Evidence">
        <Panel title={`Evidence (${report.evidence.length})`} bodyClassName="space-y-4 p-3">
          {grouped.map((group) => (
            <div key={group.kind}>
              <h3 className="mb-1.5 text-xs font-medium text-ink-muted">{KIND_LABEL[group.kind]}</h3>
              <ul className="space-y-1.5">
                {group.items.map((item) => (
                  <EvidenceCard key={item.id} item={item} active={selected === item.id} />
                ))}
              </ul>
            </div>
          ))}
        </Panel>
      </aside>
    </div>
  );
}
