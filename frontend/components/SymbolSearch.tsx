'use client';

// Global symbol search: debounced provider search, keyboard navigation,
// and a "/" shortcut to focus from anywhere. A syntactically valid symbol can
// always be opened directly even if the provider's search does not list it.

import { useEffect, useId, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Search } from 'lucide-react';
import { api, describeError } from '@/lib/api';
import { normalizeSymbol } from '@/lib/format';
import type { SymbolMatch } from '@/lib/types';

export default function SymbolSearch({
  onSelect,
  placeholder = 'Search symbols or companies',
  autoFocus = false,
  shortcut = false,
  className = '',
}: {
  onSelect?: (symbol: string, match?: SymbolMatch) => void;
  placeholder?: string;
  autoFocus?: boolean;
  shortcut?: boolean;
  className?: string;
}) {
  const router = useRouter();
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState<SymbolMatch[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!shortcut) return;
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
      if (event.key === '/' && !typing) {
        event.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [shortcut]);

  useEffect(() => {
    const text = query.trim();
    if (!text) {
      setMatches([]);
      setError(null);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      api
        .search(text, controller.signal)
        .then((results) => {
          setMatches(results);
          setError(null);
          setActive(0);
        })
        .catch((err) => {
          if (!controller.signal.aborted) {
            setMatches([]);
            setError(describeError(err));
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 220);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const direct = normalizeSymbol(query);
  const options: { symbol: string; label: string; meta: string; match?: SymbolMatch }[] = [
    ...matches.map((m) => ({
      symbol: m.symbol,
      label: m.name,
      meta: [m.quote_type, m.exchange].filter(Boolean).join(' · '),
      match: m,
    })),
  ];
  if (direct && !matches.some((m) => m.symbol === direct)) {
    options.push({ symbol: direct, label: `Open ${direct}`, meta: 'symbol' });
  }

  function choose(index: number) {
    const option = options[index];
    if (!option) return;
    setOpen(false);
    setQuery('');
    inputRef.current?.blur();
    if (onSelect) onSelect(option.symbol, option.match);
    else router.push(`/asset?symbol=${encodeURIComponent(option.symbol)}`);
  }

  return (
    <div className={`relative ${className}`}>
      <label className="sr-only" htmlFor={`${listId}-input`}>
        Search symbols
      </label>
      <div className="flex items-center gap-2 rounded border border-line bg-bg px-2.5 focus-within:border-accent">
        <Search className="h-4 w-4 shrink-0 text-ink-faint" aria-hidden />
        <input
          id={`${listId}-input`}
          ref={inputRef}
          role="combobox"
          aria-expanded={open && options.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          autoComplete="off"
          spellCheck={false}
          autoFocus={autoFocus}
          value={query}
          placeholder={placeholder}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, options.length - 1));
            } else if (e.key === 'ArrowUp') {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === 'Enter') {
              e.preventDefault();
              choose(active);
            } else if (e.key === 'Escape') {
              setOpen(false);
              inputRef.current?.blur();
            }
          }}
          className="h-8 w-full bg-transparent text-sm text-ink placeholder:text-ink-faint focus:outline-none"
        />
        {shortcut && !query && (
          <kbd className="hidden rounded border border-line px-1.5 text-2xs text-ink-faint sm:inline">/</kbd>
        )}
      </div>
      {open && query.trim() && (
        <ul
          id={listId}
          role="listbox"
          className="absolute left-0 right-0 top-full z-50 mt-1 max-h-80 overflow-auto rounded border border-line bg-raised py-1 shadow-xl shadow-black/40"
        >
          {loading && options.length === 0 && <li className="px-3 py-2 text-xs text-ink-muted">Searching…</li>}
          {error && <li className="px-3 py-2 text-xs text-down">{error}</li>}
          {!loading && !error && options.length === 0 && (
            <li className="px-3 py-2 text-xs text-ink-muted">No matches. Symbols look like AAPL, BRK-B, ^GSPC.</li>
          )}
          {options.map((option, index) => (
            <li
              key={`${option.symbol}-${index}`}
              role="option"
              aria-selected={index === active}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(index);
              }}
              onMouseEnter={() => setActive(index)}
              className={`flex cursor-pointer items-center gap-3 px-3 py-1.5 text-sm ${index === active ? 'bg-accent/10' : ''}`}
            >
              <span className="num w-20 shrink-0 font-semibold text-accent">{option.symbol}</span>
              <span className="min-w-0 flex-1 truncate text-ink">{option.label}</span>
              <span className="shrink-0 text-2xs text-ink-faint">{option.meta}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
