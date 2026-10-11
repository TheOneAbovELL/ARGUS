'use client';

import { Download } from 'lucide-react';
import { useSystem } from '@/lib/system';

/** Explains why document indexing/search is unavailable, with download progress. */
export function useEmbeddingsReady(): boolean {
  const { status } = useSystem();
  return status?.embeddings.ready ?? false;
}

export default function EmbeddingsNotice() {
  const { status } = useSystem();
  const e = status?.embeddings;
  if (!e || e.ready) return null;
  const progress =
    e.downloaded_mb != null && e.total_mb ? Math.min(100, Math.round((e.downloaded_mb / e.total_mb) * 100)) : null;
  return (
    <div role="status" className="rounded border border-warn/30 bg-warn/5 px-3 py-2 text-sm">
      <p className="flex items-center gap-1.5 font-medium text-warn">
        <Download className="h-4 w-4" aria-hidden />
        {e.status === 'downloading'
          ? 'Downloading the embedding model'
          : e.status === 'failed'
            ? 'The embedding model is unavailable'
            : 'The embedding model is not ready'}
      </p>
      <p className="mt-1 text-xs text-ink-muted">
        Uploading and searching documents needs the local embedding model ({e.provider}).
        {e.note ? ` ${e.note}` : ''}
      </p>
      {progress !== null && (
        <div className="mt-2 flex items-center gap-2">
          <div className="h-1.5 flex-1 rounded bg-raised" aria-hidden>
            <div className="h-1.5 rounded bg-warn" style={{ width: `${progress}%` }} />
          </div>
          <span className="num text-2xs text-ink-faint">
            {e.downloaded_mb?.toFixed(1)} / {e.total_mb?.toFixed(1)} MB
          </span>
        </div>
      )}
    </div>
  );
}
