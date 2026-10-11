'use client';

import { Info } from 'lucide-react';
import { useMetricDefinition } from '@/lib/metrics';
import { DASH } from '@/lib/format';

/** One headline figure in the summary strip, with the engine's formula on hover. */
export default function KeyFigure({ metric, label, value, sub, toneClass }: { metric?: string; label: string; value: string; sub?: string; toneClass?: string }) {
  const definition = useMetricDefinition(metric);
  const tooltip = definition ? `${definition.formula}\n${definition.notes}` : undefined;
  return (
    <div className="min-w-0 px-4 py-3 first:pl-0">
      <dt className="flex items-center gap-1 text-xs text-ink-muted">
        <span className="truncate">{label}</span>
        {tooltip && (
          <span title={tooltip} aria-label={`How ${label} is calculated: ${tooltip}`} tabIndex={0} className="cursor-help text-ink-faint">
            <Info className="h-3 w-3" aria-hidden />
          </span>
        )}
      </dt>
      <dd className={`num mt-1 text-xl font-semibold leading-tight ${value === DASH ? 'text-ink-faint' : toneClass ?? 'text-ink'}`}>{value}</dd>
      {sub && <dd className="mt-0.5 truncate text-2xs text-ink-faint">{sub}</dd>}
    </div>
  );
}

/** Headline strip: figures separated by rules rather than boxed tiles. */
export function KeyFigures({ children }: { children: React.ReactNode }) {
  return <dl className="grid grid-cols-2 divide-line border-y border-line sm:grid-cols-3 sm:divide-x lg:grid-cols-6">{children}</dl>;
}
