'use client';

// SEC EDGAR filings with one-click import into the user's document library.
// Hidden behind /api/system/status.sec_edgar (requires ARGUS_SEC_USER_AGENT).

import { useState } from 'react';
import Link from 'next/link';
import { Check, ExternalLink, FileDown, Landmark } from 'lucide-react';
import { api, describeError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useSystem } from '@/lib/system';
import { useAsync } from '@/lib/useAsync';
import { shortDate } from '@/lib/format';
import type { DocumentRecord, Filing } from '@/lib/types';
import { EmptyState, ErrorNotice, LoadingBlock, Panel, Spinner } from '@/components/ui';
import { useEmbeddingsReady } from '@/components/EmbeddingsNotice';

export default function FilingsPanel({ symbol, onImported }: { symbol: string; onImported?: (doc: DocumentRecord) => void }) {
  const { status } = useSystem();
  const { user } = useAuth();
  const enabled = status?.sec_edgar ?? false;
  const embeddingsReady = useEmbeddingsReady();
  const { data, error, loading, reload } = useAsync<Filing[]>(enabled ? () => api.filings(symbol) : null, [symbol, enabled]);
  const [importing, setImporting] = useState<string | null>(null);
  const [imported, setImported] = useState<Record<string, true>>({});
  const [importError, setImportError] = useState<string | null>(null);

  if (!status) return null;
  if (!enabled) {
    return (
      <Panel title="SEC filings">
        <EmptyState icon={<Landmark className="h-6 w-6" />} title="SEC EDGAR is not configured">
          The SEC requires a contact User-Agent. Set <code className="num text-ink">ARGUS_SEC_USER_AGENT</code> (e.g. &quot;Your Name
          you@example.com&quot;) on the backend to list and import official filings.
        </EmptyState>
      </Panel>
    );
  }

  async function importFiling(filing: Filing) {
    setImporting(filing.accession);
    setImportError(null);
    try {
      const doc = await api.importFiling(symbol, filing.accession);
      setImported((m) => ({ ...m, [filing.accession]: true }));
      onImported?.(doc);
    } catch (err) {
      setImportError(`${filing.form} ${shortDate(filing.filed_on)}: ${describeError(err)}`);
    } finally {
      setImporting(null);
    }
  }

  return (
    <Panel title="SEC filings (EDGAR)" bodyClassName="p-0">
      {loading && <div className="p-4"><LoadingBlock rows={4} /></div>}
      {error ? <div className="p-4"><ErrorNotice error={error} onRetry={reload} /></div> : null}
      {importError && <div className="p-3"><ErrorNotice error={new Error(importError)} compact /></div>}
      {data && data.length === 0 && (
        <EmptyState title="No filings found">EDGAR lists no 10-K/10-Q/8-K/20-F filings for {symbol} (non-US listings usually have none).</EmptyState>
      )}
      {data && data.length > 0 && (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-ink-faint">
              <th className="px-4 py-2 font-semibold">Form</th>
              <th className="px-2 py-2 font-semibold">Filed</th>
              <th className="hidden px-2 py-2 font-semibold sm:table-cell">Period</th>
              <th className="px-4 py-2 text-right font-semibold">Action</th>
            </tr>
          </thead>
          <tbody>
            {data.map((filing) => (
              <tr key={filing.accession} className="border-t border-line">
                <td className="px-4 py-2">
                  <a href={filing.url} target="_blank" rel="noopener noreferrer" className="num font-semibold text-ink hover:text-accent">
                    {filing.form} <ExternalLink className="inline h-3 w-3 text-ink-faint" aria-hidden />
                  </a>
                </td>
                <td className="num px-2 py-2 text-ink-muted">{shortDate(filing.filed_on)}</td>
                <td className="num hidden px-2 py-2 text-ink-muted sm:table-cell">{shortDate(filing.report_date)}</td>
                <td className="px-4 py-2 text-right">
                  {imported[filing.accession] ? (
                    <span className="inline-flex items-center gap-1 text-xs text-up">
                      <Check className="h-3.5 w-3.5" aria-hidden /> Imported
                    </span>
                  ) : !user ? (
                    <Link href="/login" className="text-xs text-accent hover:underline">
                      Sign in to import
                    </Link>
                  ) : importing === filing.accession ? (
                    <Spinner label="Indexing…" />
                  ) : (
                    <button type="button" className="btn-ghost px-2 py-0.5 text-xs" disabled={importing !== null || !embeddingsReady} title={embeddingsReady ? undefined : 'The embedding model is not ready yet'} onClick={() => importFiling(filing)}>
                      <FileDown className="h-3.5 w-3.5" aria-hidden /> Import
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="border-t border-line px-4 py-2 text-2xs text-ink-faint">
        Importing downloads the filing from sec.gov and indexes it for research. Large 10-Ks can take a minute.
      </p>
    </Panel>
  );
}
