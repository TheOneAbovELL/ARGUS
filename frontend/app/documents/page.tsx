'use client';

import { useRef, useState } from 'react';
import Link from 'next/link';
import { ExternalLink, FileText, Search, Trash2, Upload } from 'lucide-react';
import { api, describeError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useAsync } from '@/lib/useAsync';
import { bytes, normalizeSymbol, relativeTime, shortDate } from '@/lib/format';
import type { DocumentRecord, DocumentType, Passage } from '@/lib/types';
import FilingsPanel from '@/components/FilingsPanel';
import EmbeddingsNotice, { useEmbeddingsReady } from '@/components/EmbeddingsNotice';
import { EmptyState, ErrorNotice, LoadingBlock, PageHeader, Panel, Spinner } from '@/components/ui';

const TYPES: { value: DocumentType; label: string }[] = [
  { value: '10-K', label: '10-K annual report' },
  { value: '10-Q', label: '10-Q quarterly report' },
  { value: '8-K', label: '8-K current report' },
  { value: '20-F', label: '20-F (foreign issuer)' },
  { value: 'annual_report', label: 'Annual report' },
  { value: 'earnings_call', label: 'Earnings call transcript' },
  { value: 'investor_presentation', label: 'Investor presentation' },
  { value: 'research_note', label: 'Research note' },
  { value: 'other', label: 'Other' },
];
const MAX_MB = 15;

function UploadForm({ onUploaded }: { onUploaded: (doc: DocumentRecord) => void }) {
  const ready = useEmbeddingsReady();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [symbol, setSymbol] = useState('');
  const [type, setType] = useState<DocumentType>('10-K');
  const [title, setTitle] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [publishedOn, setPublishedOn] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const symbolOk = normalizeSymbol(symbol) !== null;
  const tooBig = file !== null && file.size > MAX_MB * 1_000_000;
  const urlOk = !sourceUrl || /^https?:\/\//.test(sourceUrl);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !symbolOk || tooBig || !urlOk) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const doc = await api.uploadDocument({
        file,
        symbol: normalizeSymbol(symbol)!,
        document_type: type,
        title: title.trim() || undefined,
        source_url: sourceUrl.trim() || undefined,
        published_on: publishedOn || undefined,
      });
      setMessage(`Indexed "${doc.title}": ${doc.page_count} page(s), ${doc.chunk_count} passages.`);
      setFile(null);
      setTitle('');
      if (fileRef.current) fileRef.current.value = '';
      onUploaded(doc);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Upload a document">
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label className="label" htmlFor="doc-file">
            File (PDF, TXT, MD, HTML · max {MAX_MB} MB)
          </label>
          <input
            id="doc-file"
            ref={fileRef}
            type="file"
            accept=".pdf,.txt,.md,.markdown,.htm,.html,application/pdf,text/plain,text/markdown,text/html"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-ink-muted file:mr-3 file:rounded file:border file:border-line file:bg-raised file:px-3 file:py-1.5 file:text-sm file:text-ink"
          />
          {tooBig && <p className="mt-1 text-2xs text-down">File is larger than {MAX_MB} MB.</p>}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="label" htmlFor="doc-symbol">
              Symbol
            </label>
            <input id="doc-symbol" className={`input num uppercase ${symbol && !symbolOk ? 'border-down' : ''}`} value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="AAPL" required />
          </div>
          <div>
            <label className="label" htmlFor="doc-date">
              Published
            </label>
            <input id="doc-date" type="date" className="input" value={publishedOn} onChange={(e) => setPublishedOn(e.target.value)} />
          </div>
        </div>
        <div>
          <label className="label" htmlFor="doc-type">
            Type
          </label>
          <select id="doc-type" className="input" value={type} onChange={(e) => setType(e.target.value as DocumentType)}>
            {TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="doc-title">
            Title <span className="normal-case tracking-normal text-ink-faint">(optional)</span>
          </label>
          <input id="doc-title" className="input" maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="doc-url">
            Source URL <span className="normal-case tracking-normal text-ink-faint">(provenance only; never fetched)</span>
          </label>
          <input id="doc-url" className={`input ${urlOk ? '' : 'border-down'}`} value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="https://…" />
        </div>
        <button type="submit" className="btn-primary w-full" disabled={!ready || !file || !symbolOk || tooBig || !urlOk || busy}>
          {busy ? <Spinner label="Parsing and indexing…" /> : (<><Upload className="h-4 w-4" aria-hidden /> Upload and index</>)}
        </button>
        {message && <p className="text-xs text-up">{message}</p>}
        {error && <p className="text-xs text-down" role="alert">{error}</p>}
        <p className="text-2xs leading-relaxed text-ink-faint">
          Text is extracted locally; scanned PDFs without a text layer cannot be read (no OCR). Documents are private to your account and are
          treated as untrusted content: quoted as evidence, never followed as instructions.
        </p>
      </form>
    </Panel>
  );
}

function SearchPanel({ symbols }: { symbols: string[] }) {
  const ready = useEmbeddingsReady();
  const [query, setQuery] = useState('');
  const [symbol, setSymbol] = useState('');
  const [result, setResult] = useState<{ passages: Passage[]; insufficient_evidence: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim().length < 2) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.searchDocuments({ query: query.trim(), symbol: symbol || undefined, limit: 8 }));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Search your documents">
      <form onSubmit={search} className="flex flex-wrap gap-2">
        <input className="input min-w-[12rem] flex-1" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. supply chain concentration risk" aria-label="Search query" />
        <select className="input w-32" value={symbol} onChange={(e) => setSymbol(e.target.value)} aria-label="Filter by symbol">
          <option value="">All symbols</option>
          {symbols.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button type="submit" className="btn-ghost" disabled={!ready || busy || query.trim().length < 2}>
          <Search className="h-4 w-4" aria-hidden /> Search
        </button>
      </form>
      <div className="mt-3 space-y-2">
        {busy && <LoadingBlock rows={3} />}
        {error ? <ErrorNotice error={error} compact /> : null}
        {result?.insufficient_evidence && (
          <p className="rounded border border-warn/30 bg-warn/5 px-3 py-2 text-sm text-ink-muted">
            No passage was relevant enough. ARGUS reports insufficient evidence rather than returning weak matches.
          </p>
        )}
        {result?.passages.map((p) => (
          <article key={p.chunk_id} className="rounded border border-line px-3 py-2">
            <header className="flex flex-wrap items-center gap-2 text-2xs text-ink-faint">
              <span className="font-semibold text-ink">{p.title}</span>
              <span>· p. {p.page_number}</span>
              <span>· {p.document_type}</span>
              <span className="num ml-auto" title={`dense ${p.dense_score.toFixed(3)} · lexical ${p.lexical_score.toFixed(3)}`}>
                relevance {p.score.toFixed(2)}
              </span>
            </header>
            <p className="mt-1 border-l-2 border-line pl-2 text-sm leading-relaxed text-ink-muted">{p.text}</p>
            <a href={api.documentFileUrl(p.document_id, p.page_number)} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-2xs text-accent hover:underline">
              Open source at page {p.page_number} <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          </article>
        ))}
      </div>
    </Panel>
  );
}

export default function DocumentsPage() {
  const { user, status } = useAuth();
  const docs = useAsync(user ? () => api.documents() : null, [user?.id]);
  const [filingsSymbol, setFilingsSymbol] = useState('');
  const [deleting, setDeleting] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (status === 'loading') return <LoadingBlock rows={4} />;
  if (!user)
    return (
      <div className="space-y-5">
        <PageHeader title="Documents" />
        <Panel>
          <EmptyState icon={<FileText className="h-7 w-7" />} title="Your private research library" action={<Link href="/login" className="btn-primary text-xs">Sign in</Link>}>
            Upload filings, transcripts and notes; ARGUS indexes them so research reports can quote and cite exact pages.
          </EmptyState>
        </Panel>
      </div>
    );

  const items = docs.data?.items ?? [];
  const symbols = Array.from(new Set(items.map((d) => d.symbol))).sort();
  const filingSymbol = normalizeSymbol(filingsSymbol);

  async function remove(doc: DocumentRecord) {
    if (!window.confirm(`Delete "${doc.title}" and its index entries?`)) return;
    setDeleting(doc.id);
    setDeleteError(null);
    try {
      await api.deleteDocument(doc.id);
      docs.setData(docs.data ? { ...docs.data, items: docs.data.items.filter((d) => d.id !== doc.id) } : null);
    } catch (err) {
      setDeleteError(describeError(err));
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader title="Documents" subtitle="Private, indexed sources for evidence-grounded research." />
      <EmbeddingsNotice />
      <div className="grid gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
        <div className="space-y-4">
          <UploadForm onUploaded={() => docs.reload()} />
          <Panel title="Import SEC filings">
            <label className="label" htmlFor="filings-symbol">
              Symbol
            </label>
            <input id="filings-symbol" className="input num uppercase" value={filingsSymbol} onChange={(e) => setFilingsSymbol(e.target.value.toUpperCase())} placeholder="MSFT" />
          </Panel>
          {filingSymbol && <FilingsPanel symbol={filingSymbol} onImported={() => docs.reload()} />}
        </div>
        <div className="min-w-0 space-y-4">
          <Panel title={`Library (${items.length})`} bodyClassName="p-0">
            {docs.loading && !docs.data && <div className="p-4"><LoadingBlock rows={4} /></div>}
            {docs.error ? <div className="p-4"><ErrorNotice error={docs.error} onRetry={docs.reload} /></div> : null}
            {deleteError && <div className="p-3"><ErrorNotice error={new Error(deleteError)} compact /></div>}
            {docs.data && items.length === 0 && <EmptyState title="No documents yet">Upload a filing or transcript to start building evidence.</EmptyState>}
            {items.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-sm">
                  <thead>
                    <tr className="text-left text-xs text-ink-faint">
                      <th className="px-4 py-2 font-semibold">Document</th>
                      <th className="px-2 py-2 font-semibold">Symbol</th>
                      <th className="px-2 py-2 font-semibold">Status</th>
                      <th className="px-2 py-2 text-right font-semibold">Pages / passages</th>
                      <th className="px-2 py-2 text-right font-semibold">Size</th>
                      <th className="w-20 px-4 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((d) => (
                      <tr key={d.id} className="border-t border-line align-top">
                        <td className="max-w-0 px-4 py-2">
                          <p className="truncate text-ink" title={d.title}>{d.title}</p>
                          <p className="truncate text-2xs text-ink-faint">
                            {d.document_type} · {d.published_on ? shortDate(d.published_on) : 'date n/a'} · added {relativeTime(d.created_at)}
                          </p>
                          {d.error && <p className="text-2xs text-down">{d.error}</p>}
                        </td>
                        <td className="num px-2 py-2 text-accent">{d.symbol}</td>
                        <td className="px-2 py-2">
                          <span className={`chip ${d.status === 'ready' ? 'border-up/40 text-up' : d.status === 'failed' ? 'border-down/40 text-down' : 'border-warn/40 text-warn'}`}>{d.status}</span>
                        </td>
                        <td className="num px-2 py-2 text-right text-ink-muted">
                          {d.page_count} / {d.chunk_count}
                        </td>
                        <td className="num px-2 py-2 text-right text-ink-muted">{bytes(d.size_bytes)}</td>
                        <td className="px-4 py-2 text-right">
                          <span className="inline-flex gap-1">
                            <a href={api.documentFileUrl(d.id)} target="_blank" rel="noopener noreferrer" aria-label={`Open ${d.title}`} className="rounded p-1 text-ink-faint hover:text-accent">
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                            <button type="button" aria-label={`Delete ${d.title}`} disabled={deleting === d.id} onClick={() => remove(d)} className="rounded p-1 text-ink-faint hover:text-down">
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
          <SearchPanel symbols={symbols} />
        </div>
      </div>
    </div>
  );
}
