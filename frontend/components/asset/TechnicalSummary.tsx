'use client';

import { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import type { TechnicalSignal, Technicals } from '@/lib/types';

const TONE: Record<TechnicalSignal['tone'], { dot: string; text: string; word: string }> = {
  positive: { dot: 'bg-up', text: 'text-up', word: 'Up-trend reading' },
  negative: { dot: 'bg-down', text: 'text-down', word: 'Down-trend reading' },
  neutral: { dot: 'bg-ink-faint', text: 'text-ink', word: 'Neutral' },
};

function SignalRow({ signal }: { signal: TechnicalSignal }) {
  const [open, setOpen] = useState(false);
  const tone = TONE[signal.tone];
  return (
    <li className="border-b border-line/60 last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 py-2 text-left hover:bg-raised/40"
      >
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${tone.dot}`} title={tone.word} aria-hidden />
        <span className="min-w-0 flex-1 text-[13px] text-ink-muted">{signal.label}</span>
        <span className={`num text-[13px] font-medium ${tone.text}`}>{signal.value}</span>
        <ChevronRight className={`h-3.5 w-3.5 shrink-0 text-ink-faint transition-transform ${open ? 'rotate-90' : ''}`} aria-hidden />
      </button>
      {open && (
        <div className="space-y-1.5 pb-3 pl-3.5 pr-1 text-[13px] leading-relaxed">
          <p className="text-ink">{signal.reading}</p>
          <p className="text-xs text-ink-faint">How it is calculated: {signal.method}</p>
        </div>
      )}
    </li>
  );
}

export default function TechnicalSummary({ data }: { data: Technicals }) {
  const counts = data.signals.reduce(
    (acc, s) => ({ ...acc, [s.tone]: acc[s.tone] + 1 }),
    { positive: 0, negative: 0, neutral: 0 } as Record<TechnicalSignal['tone'], number>,
  );
  const directional = counts.positive + counts.negative;
  return (
    <section aria-label="Technical summary" className="space-y-3">
      <div>
        <h2 className="text-[13px] font-semibold text-ink">Technical summary</h2>
        <p className="mt-0.5 text-xs text-ink-faint">As of {data.as_of} close · tap a row for the explanation</p>
      </div>
      {directional > 0 && (
        <div>
          <div className="flex h-1.5 overflow-hidden rounded-full bg-line" aria-hidden>
            <div className="bg-up" style={{ width: `${(counts.positive / directional) * 100}%` }} />
            <div className="bg-down" style={{ width: `${(counts.negative / directional) * 100}%` }} />
          </div>
          <p className="mt-1.5 text-xs text-ink-muted">
            <span className="text-up">{counts.positive} up-trend</span> · <span className="text-down">{counts.negative} down-trend</span> ·{' '}
            {counts.neutral} neutral readings
          </p>
        </div>
      )}
      <ul>
        {data.signals.map((s) => (
          <SignalRow key={s.key} signal={s} />
        ))}
      </ul>
      <p className="text-2xs leading-relaxed text-ink-faint">{data.conventions}</p>
    </section>
  );
}
