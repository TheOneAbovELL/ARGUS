import { freshness, MODE_LABEL } from '@/lib/format';
import type { Provenance } from '@/lib/types';

/** Compact, honest freshness indicator. Hover/focus shows full provenance. */
export default function DataBadge({ provenance, showProvider = false }: { provenance: Provenance; showProvider?: boolean }) {
  const tone =
    provenance.mode === 'fixture'
      ? 'border-synthetic/40 bg-synthetic/10 text-synthetic'
      : provenance.stale
        ? 'border-warn/40 bg-warn/10 text-warn'
        : 'border-line bg-raised text-ink-muted';
  const description = freshness(provenance);
  return (
    <span className={`chip ${tone}`} title={description} aria-label={description} tabIndex={0}>
      <span
        className={`h-1.5 w-1.5 rounded-full ${provenance.mode === 'fixture' ? 'bg-synthetic' : provenance.stale ? 'bg-warn' : 'bg-up'}`}
        aria-hidden
      />
      {provenance.stale ? 'Stale' : MODE_LABEL[provenance.mode]}
      {provenance.mode === 'fixture' && <span className="font-normal">· not market prices</span>}
      {showProvider && <span className="font-normal text-ink-faint">· {provenance.provider}</span>}
    </span>
  );
}
