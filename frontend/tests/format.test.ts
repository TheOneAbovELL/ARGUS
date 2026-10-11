import { describe, expect, it } from 'vitest';
import { compact, DASH, freshness, normalizeSymbol, num, pct, relativeTime, signClass } from '@/lib/format';
import type { Provenance } from '@/lib/types';

const base: Provenance = {
  provider: 'Yahoo Finance (yfinance)',
  mode: 'delayed',
  retrieved_at: '2026-10-10T12:00:00Z',
  as_of: '2026-10-09T20:00:00Z',
  cached: false,
  stale: false,
};

describe('number formatting', () => {
  it('formats decimal returns as percentages', () => {
    expect(pct(0.1234)).toBe('12.34%');
    expect(pct(-0.05, 1)).toBe('-5.0%');
    expect(pct(0.02, 2, true)).toBe('+2.00%');
  });

  it('renders undefined metrics as a dash, never zero', () => {
    expect(pct(null)).toBe(DASH);
    expect(num(undefined)).toBe(DASH);
    expect(pct(Number.NaN)).toBe(DASH);
    expect(num(Number.POSITIVE_INFINITY)).toBe(DASH);
  });

  it('compacts large values with units', () => {
    expect(compact(3_973_186_846_720, 'USD')).toBe('3.97T USD');
    expect(compact(2_500_000)).toBe('2.50M');
    expect(compact(950)).toBe('950');
  });

  it('uses crore / lakh with the rupee sign for INR', () => {
    expect(compact(15_842_070_000_000, 'INR')).toBe('₹15,84,207 Cr');
    expect(compact(123_456_789, 'INR')).toBe('₹12.35 Cr');
    expect(compact(250_000, 'INR')).toBe('₹2.5 L');
  });

  it('colors only signed, finite values', () => {
    expect(signClass(0.01)).toBe('text-up');
    expect(signClass(-0.01)).toBe('text-down');
    expect(signClass(null)).toBe('text-ink-muted');
    expect(signClass(0)).toBe('text-ink-muted');
  });
});

describe('symbols', () => {
  it('accepts the formats the backend accepts', () => {
    for (const s of ['aapl', 'BRK-B', '^GSPC', 'BTC-USD', 'RELIANCE.NS', 'EURUSD=X']) {
      expect(normalizeSymbol(s)).toBe(s.toUpperCase());
    }
  });

  it('rejects malformed symbols', () => {
    for (const s of ['', '   ', 'NVDA!', 'A'.repeat(16), '-ABC', 'a b']) {
      expect(normalizeSymbol(s)).toBeNull();
    }
  });
});

describe('freshness', () => {
  it('never describes delayed data as real-time', () => {
    const text = freshness(base);
    expect(text).toContain('Delayed quote — not real-time');
    expect(text.replace('not real-time', '')).not.toMatch(/real-time/i);
  });

  it('labels synthetic data unmistakably', () => {
    expect(freshness({ ...base, mode: 'fixture' })).toContain('not market prices');
  });

  it('flags stale cache fallbacks', () => {
    expect(freshness({ ...base, stale: true, cached: true })).toContain('STALE');
  });

  it('computes relative time', () => {
    const now = new Date('2026-10-10T12:00:00Z');
    expect(relativeTime('2026-10-10T11:59:30Z', now)).toBe('just now');
    expect(relativeTime('2026-10-10T11:00:00Z', now)).toBe('1h ago');
    expect(relativeTime('2026-10-08T12:00:00Z', now)).toBe('2d ago');
  });
});
