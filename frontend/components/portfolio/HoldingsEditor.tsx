'use client';

import { Plus, Trash2 } from 'lucide-react';
import { equalWeights, scaleTo100, type DraftHolding, type HoldingsValidation } from '@/lib/holdings';

export default function HoldingsEditor({
  rows,
  onChange,
  validation,
}: {
  rows: DraftHolding[];
  onChange: (rows: DraftHolding[]) => void;
  validation: HoldingsValidation;
}) {
  const nextId = () => Math.max(0, ...rows.map((r) => r.id)) + 1;
  const update = (id: number, patch: Partial<DraftHolding>) => onChange(rows.map((r) => (r.id === id ? { ...r, ...patch } : r)));

  const equalWeight = () => {
    const weights = equalWeights(rows.length);
    onChange(rows.map((r, i) => ({ ...r, weight: String(weights[i]) })));
  };
  const normalize = () => {
    const scaled = scaleTo100(rows.map((r) => Number(r.weight)));
    if (scaled) onChange(rows.map((r, i) => ({ ...r, weight: String(scaled[i]) })));
  };

  const totalClass = Math.abs(validation.total - 100) <= 0.01 ? 'text-up' : 'text-warn';

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-[1fr_6.5rem_2rem] gap-2 text-xs text-ink-faint">
        <span>Symbol</span>
        <span className="text-right">Weight %</span>
        <span />
      </div>
      <ul className="space-y-1.5">
        {rows.map((row) => {
          const err = validation.rows[row.id];
          return (
            <li key={row.id}>
              <div className="grid grid-cols-[1fr_6.5rem_2rem] gap-2">
                <input
                  aria-label="Symbol"
                  aria-invalid={!!err}
                  className={`input num uppercase ${err ? 'border-down' : ''}`}
                  value={row.symbol}
                  placeholder="AAPL"
                  onChange={(e) => update(row.id, { symbol: e.target.value.toUpperCase() })}
                />
                <input
                  aria-label={`Weight for ${row.symbol || 'holding'}`}
                  className="input num text-right"
                  inputMode="decimal"
                  value={row.weight}
                  onChange={(e) => update(row.id, { weight: e.target.value })}
                />
                <button
                  type="button"
                  aria-label={`Remove ${row.symbol || 'row'}`}
                  className="grid place-items-center rounded text-ink-faint hover:bg-raised hover:text-down"
                  onClick={() => onChange(rows.filter((r) => r.id !== row.id))}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
              {err && <p className="mt-0.5 text-2xs text-down">{err}</p>}
            </li>
          );
        })}
      </ul>
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button type="button" className="btn-ghost px-2 py-1 text-xs" disabled={rows.length >= 30} onClick={() => onChange([...rows, { id: nextId(), symbol: '', weight: '' }])}>
          <Plus className="h-3.5 w-3.5" aria-hidden /> Add
        </button>
        <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={equalWeight} disabled={!rows.length}>
          Equal weight
        </button>
        <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={normalize} disabled={!rows.length}>
          Scale to 100%
        </button>
        <span className={`num ml-auto text-xs ${totalClass}`}>Σ {validation.total.toFixed(2)}%</span>
      </div>
    </div>
  );
}
