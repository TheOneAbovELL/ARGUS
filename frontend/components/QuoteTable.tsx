'use client';

import Link from 'next/link';
import { X } from 'lucide-react';
import { currencySymbol, pct, price, signClass } from '@/lib/format';
import type { QuoteResult } from '@/lib/types';

/** Kite-style market watch: name, last price, absolute and percent change. */
export default function QuoteTable({
  results,
  onRemove,
  labels = {},
}: {
  results: QuoteResult[];
  onRemove?: (symbol: string) => void;
  /** Friendlier display names for index tickers, e.g. ^NSEI → NIFTY 50. */
  labels?: Record<string, string>;
}) {
  // Scale the change bars to the largest move in this list so they compare at a glance.
  const maxMove = Math.max(0.005, ...results.map((r) => Math.abs(r.quote?.change_percent ?? 0)));
  return (
    <table className="w-full text-[13px]">
      <thead>
        <tr className="text-left text-xs text-ink-faint">
          <th className="py-2 pl-4 pr-2 font-normal">Instrument</th>
          <th className="px-2 py-2 text-right font-normal">Last</th>
          <th className="px-2 py-2 text-right font-normal">Change</th>
          <th className="hidden w-24 px-2 py-2 font-normal sm:table-cell" aria-label="Change bar" />
          {onRemove && <th className="w-8 px-2" aria-label="Remove" />}
        </tr>
      </thead>
      <tbody>
        {results.map(({ symbol, quote, error }) => {
          const move = quote?.change_percent ?? null;
          const width = move === null ? 0 : (Math.abs(move) / maxMove) * 50;
          // Skip the friendly label when the provider name already says the same thing (e.g. "NIFTY 50").
          const label = labels[symbol] && !quote?.name?.toUpperCase().includes(labels[symbol].toUpperCase()) ? labels[symbol] : null;
          return (
            <tr key={symbol} className="group border-t border-line/70 hover:bg-raised/40">
              <td className="max-w-0 py-2 pl-4 pr-2">
                <Link href={`/asset?symbol=${encodeURIComponent(symbol)}`} className="block">
                  <span className="font-medium text-ink group-hover:text-accent">{symbol}</span>
                  {label && <span className="ml-1.5 text-xs text-ink-muted">{label}</span>}
                  <span className={`block truncate text-2xs ${quote ? 'text-ink-faint' : 'text-down'}`}>
                    {quote ? quote.name : error ? `Unavailable: ${error}` : ''}
                  </span>
                </Link>
              </td>
              <td className="num px-2 py-2 text-right font-medium text-ink">
                {quote ? (
                  <>
                    <span className="text-ink-faint">{currencySymbol(quote.currency)}</span>
                    {price(quote.price)}
                  </>
                ) : (
                  '—'
                )}
              </td>
              <td className={`num px-2 py-2 text-right ${signClass(move)}`}>
                {quote ? (
                  <>
                    <span className="block">{pct(move, 2, true)}</span>
                    {quote.change !== null && (
                      <span className="block text-2xs opacity-80">
                        {quote.change > 0 ? '+' : ''}
                        {quote.change.toFixed(2)}
                      </span>
                    )}
                  </>
                ) : (
                  '—'
                )}
              </td>
              <td className="hidden px-2 py-2 sm:table-cell" aria-hidden>
                <div className="relative h-1.5 rounded-full bg-line/50">
                  <div className="absolute inset-y-0 left-1/2 w-px bg-ink-faint/50" />
                  {move !== null && move !== 0 && (
                    <div
                      className={`absolute inset-y-0 rounded-full ${move > 0 ? 'left-1/2 bg-up' : 'right-1/2 bg-down'}`}
                      style={{ width: `${width}%` }}
                    />
                  )}
                </div>
              </td>
              {onRemove && (
                <td className="px-2 py-2">
                  <button
                    type="button"
                    aria-label={`Remove ${symbol}`}
                    onClick={() => onRemove(symbol)}
                    className="rounded p-1 text-ink-faint opacity-60 hover:bg-bg hover:text-down group-hover:opacity-100"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </td>
              )}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
