// Per-browser convenience: recently viewed symbols. Best effort only — storage
// may be unavailable, and nothing important depends on it.

const KEY = 'argus_recent_symbols';
const MAX = 8;

export function readRecent(): string[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((s) => typeof s === 'string').slice(0, MAX) : [];
  } catch {
    return [];
  }
}

export function pushRecent(symbol: string): void {
  try {
    const next = [symbol, ...readRecent().filter((s) => s !== symbol)].slice(0, MAX);
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // ignore
  }
}
