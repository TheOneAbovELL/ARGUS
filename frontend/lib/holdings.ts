// Client-side allocation checks that mirror the backend's rules, so users get
// immediate feedback. The backend validates again; this is UX, not authority.

import { normalizeSymbol } from './format';

export interface DraftHolding {
  id: number;
  symbol: string;
  weight: string; // percent, as typed
}

export interface HoldingsValidation {
  valid: boolean;
  total: number;
  errors: string[];
  rows: Record<number, string | undefined>;
}

export const MAX_HOLDINGS = 30;
export const WEIGHT_TOLERANCE = 0.01;

export function validateHoldings(rows: DraftHolding[]): HoldingsValidation {
  const errors: string[] = [];
  const rowErrors: Record<number, string | undefined> = {};
  const seen = new Set<string>();
  let total = 0;
  for (const row of rows) {
    const symbol = normalizeSymbol(row.symbol);
    const weight = row.weight.trim() === '' ? NaN : Number(row.weight);
    if (!symbol) rowErrors[row.id] = 'Invalid symbol';
    else if (seen.has(symbol)) rowErrors[row.id] = 'Duplicate';
    else if (!Number.isFinite(weight) || weight <= 0 || weight > 100) rowErrors[row.id] = 'Weight must be in (0, 100]';
    if (symbol) seen.add(symbol);
    if (Number.isFinite(weight)) total += weight;
  }
  if (rows.length === 0) errors.push('Add at least one holding.');
  if (rows.length > MAX_HOLDINGS) errors.push(`At most ${MAX_HOLDINGS} holdings.`);
  if (Object.values(rowErrors).some(Boolean)) errors.push('Fix the highlighted rows.');
  if (rows.length && Math.abs(total - 100) > WEIGHT_TOLERANCE) errors.push(`Weights sum to ${total.toFixed(2)}%; they must sum to 100%.`);
  return { valid: errors.length === 0, total, errors, rows: rowErrors };
}

/** Equal weights in hundredths of a percent; any rounding remainder goes to the first row. */
export function equalWeights(count: number): number[] {
  if (count <= 0) return [];
  const base = Math.floor(10000 / count) / 100;
  const remainder = Math.round((100 - base * count) * 100) / 100;
  return Array.from({ length: count }, (_, i) => (i === 0 ? Math.round((base + remainder) * 100) / 100 : base));
}

/** Rescale positive weights proportionally so they sum to exactly 100. */
export function scaleTo100(weights: number[]): number[] | null {
  const total = weights.reduce((sum, w) => sum + (Number.isFinite(w) && w > 0 ? w : 0), 0);
  if (total <= 0) return null;
  const scaled = weights.map((w) => Math.round(((Number.isFinite(w) && w > 0 ? w : 0) / total) * 10000) / 100);
  const drift = Math.round((100 - scaled.reduce((a, b) => a + b, 0)) * 100) / 100;
  scaled[0] = Math.round((scaled[0] + drift) * 100) / 100;
  return scaled;
}
