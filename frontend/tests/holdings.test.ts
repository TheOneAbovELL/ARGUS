import { describe, expect, it } from 'vitest';
import { equalWeights, scaleTo100, validateHoldings, type DraftHolding } from '@/lib/holdings';

const rows = (...pairs: [string, string][]): DraftHolding[] => pairs.map(([symbol, weight], i) => ({ id: i + 1, symbol, weight }));

describe('validateHoldings', () => {
  it('accepts a valid allocation that sums to 100', () => {
    const v = validateHoldings(rows(['SPY', '60'], ['TLT', '40']));
    expect(v.valid).toBe(true);
    expect(v.total).toBe(100);
  });

  it('allows the same 0.01 tolerance as the API', () => {
    expect(validateHoldings(rows(['A', '33.33'], ['B', '33.33'], ['C', '33.33'])).valid).toBe(false);
    expect(validateHoldings(rows(['A', '33.34'], ['B', '33.33'], ['C', '33.33'])).valid).toBe(true);
  });

  it('flags duplicates, bad symbols, and out-of-range weights per row', () => {
    const v = validateHoldings(rows(['SPY', '50'], ['spy', '50'], ['BAD!', '10'], ['QQQ', '0']));
    expect(v.valid).toBe(false);
    expect(v.rows[2]).toBe('Duplicate');
    expect(v.rows[3]).toBe('Invalid symbol');
    expect(v.rows[4]).toMatch(/Weight/);
  });

  it('treats a blank weight as missing, not zero-but-valid', () => {
    const v = validateHoldings(rows(['SPY', '100'], ['TLT', '']));
    expect(v.valid).toBe(false);
    expect(v.rows[2]).toMatch(/Weight/);
  });

  it('rejects empty and oversized portfolios', () => {
    expect(validateHoldings([]).valid).toBe(false);
    const many = Array.from({ length: 31 }, (_, i) => ({ id: i, symbol: `S${i}`, weight: String(100 / 31) }));
    expect(validateHoldings(many).errors.join(' ')).toMatch(/At most 30/);
  });
});

describe('weight helpers', () => {
  it('equal weights always sum to exactly 100', () => {
    for (const n of [1, 3, 6, 7, 30]) {
      const sum = equalWeights(n).reduce((a, b) => a + b, 0);
      expect(Math.round(sum * 100) / 100).toBe(100);
    }
  });

  it('scaling preserves proportions and sums to 100', () => {
    const scaled = scaleTo100([1, 1, 2])!;
    expect(scaled).toEqual([25, 25, 50]);
    expect(scaleTo100([0, 0])).toBeNull();
    const odd = scaleTo100([1, 1, 1])!;
    expect(Math.round(odd.reduce((a, b) => a + b, 0) * 100) / 100).toBe(100);
  });
});
