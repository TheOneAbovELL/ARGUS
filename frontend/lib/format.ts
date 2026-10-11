// Display formatting. Formatting only — never recompute financial metrics here.

import type { DataMode, Provenance } from './types';

export const DASH = '—';

const isNum = (v: number | null | undefined): v is number => typeof v === 'number' && Number.isFinite(v);

export function pct(value: number | null | undefined, digits = 2, signed = false): string {
  if (!isNum(value)) return DASH;
  const text = `${(value * 100).toFixed(digits)}%`;
  return signed && value > 0 ? `+${text}` : text;
}

export function num(value: number | null | undefined, digits = 2): string {
  if (!isNum(value)) return DASH;
  return value.toFixed(digits);
}

export function price(value: number | null | undefined, currency?: string | null): string {
  if (!isNum(value)) return DASH;
  const digits = Math.abs(value) >= 1000 ? 2 : Math.abs(value) >= 1 ? 2 : 4;
  const text = value.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return currency ? `${text} ${currency}` : text;
}

/** Indian units (as on Kite / Groww): crore = 1e7, lakh = 1e5. */
export function indianCompact(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e7) return `${(value / 1e7).toLocaleString('en-IN', { maximumFractionDigits: abs >= 1e10 ? 0 : 2 })} Cr`;
  if (abs >= 1e5) return `${(value / 1e5).toLocaleString('en-IN', { maximumFractionDigits: 2 })} L`;
  return value.toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

export function compact(value: number | null | undefined, currency?: string | null): string {
  if (!isNum(value)) return DASH;
  if (currency === 'INR') return `₹${indianCompact(value)}`;
  const abs = Math.abs(value);
  const [scaled, suffix] =
    abs >= 1e12 ? [value / 1e12, 'T'] : abs >= 1e9 ? [value / 1e9, 'B'] : abs >= 1e6 ? [value / 1e6, 'M'] : abs >= 1e3 ? [value / 1e3, 'K'] : [value, ''];
  const text = `${scaled.toFixed(suffix ? 2 : 0)}${suffix}`;
  return currency ? `${text} ${currency}` : text;
}

export function signClass(value: number | null | undefined): string {
  if (!isNum(value) || value === 0) return 'text-ink-muted';
  return value > 0 ? 'text-up' : 'text-down';
}

export function bytes(size: number): string {
  if (size >= 1e6) return `${(size / 1e6).toFixed(1)} MB`;
  if (size >= 1e3) return `${(size / 1e3).toFixed(0)} KB`;
  return `${size} B`;
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' });
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function relativeTime(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return DASH;
  const then = new Date(iso);
  const seconds = Math.round((now.getTime() - then.getTime()) / 1000);
  if (!Number.isFinite(seconds)) return iso;
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export const MODE_LABEL: Record<DataMode, string> = {
  delayed: 'Delayed',
  end_of_day: 'End of day',
  fixture: 'Synthetic',
};

/** One-line, honest description of a payload's freshness. */
export function freshness(p: Provenance): string {
  const parts: string[] = [];
  if (p.mode === 'fixture') parts.push('Synthetic fixture data — not market prices');
  else if (p.mode === 'delayed') parts.push('Delayed quote — not real-time');
  else parts.push('Daily bars');
  if (p.as_of) parts.push(`as of ${p.as_of.length === 10 ? shortDate(p.as_of) : dateTime(p.as_of)}`);
  parts.push(`source: ${p.provider}`);
  if (p.stale) parts.push('STALE: provider unavailable, showing last cached copy');
  else if (p.cached) parts.push(`cached, retrieved ${relativeTime(p.retrieved_at)}`);
  return parts.join(' · ');
}

export const PERIODS = ['1mo', '3mo', '6mo', 'ytd', '1y', '2y', '3y', '5y', '10y', 'max'] as const;
export type Period = (typeof PERIODS)[number];

const SYMBOL_RE = /^[A-Z0-9^][A-Z0-9.\-=^]{0,14}$/;
export function normalizeSymbol(raw: string): string | null {
  const s = raw.trim().toUpperCase();
  return SYMBOL_RE.test(s) ? s : null;
}

const CURRENCY_SYMBOL: Record<string, string> = { INR: '₹', USD: '$', EUR: '€', GBP: '£', JPY: '¥' };
export function currencySymbol(currency: string | null | undefined): string {
  return (currency && CURRENCY_SYMBOL[currency]) || '';
}

/** Counts (shares, volume) in the market's convention: lakh/crore for INR. */
export function count(value: number | null | undefined, currency?: string | null): string {
  if (!isNum(value)) return DASH;
  return currency === 'INR' ? indianCompact(value) : compact(value);
}
