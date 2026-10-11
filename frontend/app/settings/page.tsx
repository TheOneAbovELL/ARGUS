'use client';

import { useEffect, useState } from 'react';
import { api, getApiBase, setCustomApiBase } from '@/lib/api';
import { useSystem } from '@/lib/system';
import { useMetricDefinitions } from '@/lib/metrics';
import { PageHeader, Panel } from '@/components/ui';

function ConnectionPanel() {
  const { reload } = useSystem();
  const [base, setBase] = useState('');
  const [input, setInput] = useState('');
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  const envLocked = Boolean(process.env.NEXT_PUBLIC_API_URL);

  useEffect(() => {
    const current = getApiBase();
    setBase(current);
    setInput(current);
  }, []);

  async function test(target: string) {
    setResult(null);
    try {
      await api.health(target);
      setResult({ ok: true, text: `Connected to ${target || 'this origin'}.` });
      return true;
    } catch {
      setResult({ ok: false, text: `No ARGUS backend responded at ${target || 'this origin'}.` });
      return false;
    }
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const value = input.trim().replace(/\/$/, '');
    if (value && !/^https?:\/\//.test(value)) {
      setResult({ ok: false, text: 'Enter an http(s) URL, or leave empty to auto-detect.' });
      return;
    }
    if (await test(value)) {
      setCustomApiBase(value);
      setBase(getApiBase());
      reload();
    }
  }

  return (
    <Panel title="Backend connection" className="min-w-0">
      <form onSubmit={save} className="space-y-3">
        <p className="text-sm text-ink-muted">
          Current API base: <span className="num break-all text-ink">{base || '(same origin)'}</span>
          {envLocked && ' — fixed by NEXT_PUBLIC_API_URL at build time.'}
        </p>
        {!envLocked && (
          <>
            <div className="flex flex-wrap gap-2">
              <input className="input num min-w-0 flex-1" value={input} onChange={(e) => setInput(e.target.value)} placeholder="http://localhost:8000 (empty = auto-detect)" aria-label="Backend URL" />
              <button type="submit" className="btn-primary">
                Test & save
              </button>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => {
                  setCustomApiBase('');
                  setInput(getApiBase());
                  setBase(getApiBase());
                  reload();
                  setResult({ ok: true, text: 'Reset to auto-detect.' });
                }}
              >
                Reset
              </button>
            </div>
            <p className="text-2xs text-ink-faint">
              Stored in this browser only. Cross-origin backends must list this site in ARGUS_CORS_ORIGINS for sign-in cookies to work.
            </p>
          </>
        )}
        {result && <p className={`text-sm ${result.ok ? 'text-up' : 'text-down'}`}>{result.text}</p>}
      </form>
    </Panel>
  );
}

function CapabilitiesPanel() {
  const { status, reachable, reload } = useSystem();
  return (
    <Panel title="Capabilities" className="min-w-0" actions={<button type="button" className="text-2xs text-ink-muted hover:text-accent" onClick={reload}>Refresh</button>}>
      {reachable === false && <p className="text-sm text-down">Backend unreachable.</p>}
      {status && (
        <dl className="grid grid-cols-[minmax(0,7.5rem)_minmax(0,1fr)] gap-x-4 gap-y-2 break-words text-sm sm:grid-cols-[10rem_minmax(0,1fr)]">
          <dt className="text-ink-muted">Version</dt>
          <dd className="num">{status.version} ({status.environment})</dd>
          <dt className="text-ink-muted">Market data</dt>
          <dd>
            {status.market_data.provider}
            <span className="block text-2xs text-ink-faint">{status.market_data.note}</span>
          </dd>
          <dt className="text-ink-muted">Research synthesis</dt>
          <dd>
            {status.research.mode === 'llm' ? `${status.research.llm_provider} · ${status.research.llm_model}` : 'Deterministic agents (no language model)'}
            <span className="block text-2xs text-ink-faint">
              ARGUS never calls paid model APIs. An optional local model (e.g. Ollama) can be enabled on the backend.
            </span>
          </dd>
          <dt className="text-ink-muted">Embeddings</dt>
          <dd>
            {status.embeddings.provider} · {status.embeddings.ready ? 'ready' : status.embeddings.status}
            {status.embeddings.note && <span className="block text-2xs text-ink-faint">{status.embeddings.note}</span>}
          </dd>
          <dt className="text-ink-muted">SEC EDGAR</dt>
          <dd>{status.sec_edgar ? 'Enabled' : 'Disabled — set ARGUS_SEC_USER_AGENT on the backend'}</dd>
        </dl>
      )}
    </Panel>
  );
}

function GlossaryPanel() {
  const definitions = Object.values(useMetricDefinitions());
  if (!definitions.length) return null;
  return (
    <Panel title="Metric definitions & conventions" bodyClassName="p-0">
      <dl className="divide-y divide-line">
        {definitions.map((d) => (
          <div key={d.key} className="grid gap-1 px-4 py-2.5 md:grid-cols-[12rem_1fr]">
            <dt className="text-sm font-medium text-ink">{d.label}</dt>
            <dd className="space-y-0.5">
              <p className="num text-xs text-accent">{d.formula}</p>
              <p className="text-xs text-ink-muted">{d.notes}</p>
            </dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

export default function SettingsPage() {
  return (
    <div className="space-y-5">
      <PageHeader title="Settings" subtitle="Connection, capabilities and calculation conventions." />
      <div className="grid gap-4 lg:grid-cols-2">
        <ConnectionPanel />
        <CapabilitiesPanel />
      </div>
      <GlossaryPanel />
    </div>
  );
}
