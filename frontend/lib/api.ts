// Typed client for the ARGUS API. All network access goes through `request`
// so errors, timeouts, credentials and the CSRF header are handled uniformly.

import type {
  AssetAnalysis,
  DocumentRecord,
  DocumentType,
  Filing,
  History,
  HoldingInput,
  MetricDefinition,
  NewsFeed,
  PageMeta,
  Passage,
  PortfolioAnalysis,
  Profile,
  Quote,
  QuoteResult,
  RebalancingModel,
  ResearchReport,
  ResearchStep,
  ResearchSummary,
  SavedPortfolio,
  SessionInfo,
  StressResult,
  SymbolMatch,
  SystemStatus,
  Technicals,
  User,
  WatchlistItem,
} from './types';
import { readEventStream } from './sse';

// ─── Base URL ────────────────────────────────────────────────

const BACKEND_URL_KEY = 'argus_backend_url';

export function getApiBase(): string {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, '');
  }
  if (typeof window !== 'undefined') {
    try {
      const custom = window.localStorage.getItem(BACKEND_URL_KEY);
      if (custom) return custom.trim().replace(/\/$/, '');
    } catch {
      // storage unavailable (private mode) — fall through to auto-detect
    }
    // `next dev` runs on :3000 while the API runs on :8000.
    if (window.location.port === '3000') return 'http://localhost:8000';
    return ''; // same origin: FastAPI serves the exported UI
  }
  return 'http://localhost:8000';
}

export function setCustomApiBase(url: string): void {
  if (typeof window === 'undefined') return;
  try {
    if (url.trim()) window.localStorage.setItem(BACKEND_URL_KEY, url.trim());
    else window.localStorage.removeItem(BACKEND_URL_KEY);
  } catch {
    // ignore: the setting simply won't persist
  }
}

// ─── Errors ──────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly requestId: string | null = null,
    public readonly details: unknown = null,
    public readonly retryAfter: number | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
  }

  get isAuth(): boolean {
    return this.status === 401;
  }
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string; details?: unknown };
  request_id?: string | null;
  detail?: unknown;
}

export function errorFromBody(status: number, body: unknown, requestId: string | null, retryAfter: number | null): ApiError {
  const envelope = (body ?? {}) as ErrorEnvelope;
  if (envelope.error?.message) {
    return new ApiError(
      envelope.error.message,
      status,
      envelope.error.code ?? 'http_error',
      envelope.request_id ?? requestId,
      envelope.error.details ?? null,
      retryAfter,
    );
  }
  const fallback =
    status >= 500
      ? 'The server could not complete the request.'
      : status === 404
        ? 'Not found.'
        : `Request failed (HTTP ${status}).`;
  return new ApiError(fallback, status, 'http_error', requestId, null, retryAfter);
}

/** A short, user-facing explanation including the request id for support. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    let text = error.message;
    if (error.code === 'rate_limited' && error.retryAfter) text += ` Retry in ${error.retryAfter}s.`;
    return text;
  }
  if (error instanceof Error) return error.message;
  return 'Something went wrong.';
}

// ─── Core request ────────────────────────────────────────────

const MUTATING = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

interface RequestOptions {
  method?: string;
  body?: unknown;
  form?: FormData;
  timeoutMs?: number;
  signal?: AbortSignal;
}

function buildHeaders(method: string, json: boolean): Record<string, string> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (json) headers['Content-Type'] = 'application/json';
  if (MUTATING.has(method)) headers['X-ARGUS-CSRF'] = '1';
  return headers;
}

function linkSignals(timeoutMs: number, external?: AbortSignal): { signal: AbortSignal; cancel: () => void; timedOut: () => boolean } {
  const controller = new AbortController();
  let expired = false;
  const timer = setTimeout(() => {
    expired = true;
    controller.abort();
  }, timeoutMs);
  const onAbort = () => controller.abort();
  external?.addEventListener('abort', onAbort);
  return {
    signal: controller.signal,
    cancel: () => {
      clearTimeout(timer);
      external?.removeEventListener('abort', onAbort);
    },
    timedOut: () => expired,
  };
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? (options.body !== undefined || options.form ? 'POST' : 'GET');
  const link = linkSignals(options.timeoutMs ?? 30_000, options.signal);
  let response: Response;
  try {
    response = await fetch(`${getApiBase()}${path}`, {
      method,
      credentials: 'include',
      headers: buildHeaders(method, options.body !== undefined),
      body: options.form ?? (options.body !== undefined ? JSON.stringify(options.body) : undefined),
      signal: link.signal,
      cache: 'no-store',
    });
  } catch (error) {
    link.cancel();
    if (link.timedOut()) throw new ApiError('The request timed out. Please try again.', 0, 'timeout');
    if (options.signal?.aborted) throw new ApiError('Request cancelled.', 0, 'cancelled');
    throw new ApiError(
      'Cannot reach the ARGUS backend. Check that it is running and the connection settings are correct.',
      0,
      'network_error',
    );
  }
  link.cancel();
  const requestId = response.headers.get('x-request-id');
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }
  if (!response.ok) {
    const retry = Number(response.headers.get('retry-after'));
    throw errorFromBody(response.status, body, requestId, Number.isFinite(retry) && retry > 0 ? retry : null);
  }
  return body as T;
}

const q = (params: Record<string, string | number | boolean | null | undefined>): string => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : '';
};

const seg = encodeURIComponent;

// ─── System ──────────────────────────────────────────────────

export const api = {
  health: (base?: string) =>
    fetch(`${(base ?? getApiBase()).replace(/\/$/, '')}/health`, { cache: 'no-store' }).then((r) => {
      if (!r.ok) throw new Error('Backend unavailable');
      return r.json() as Promise<{ status: string }>;
    }),
  status: () => request<SystemStatus>('/api/system/status'),
  metricDefinitions: () => request<MetricDefinition[]>('/api/meta/metrics'),

  // ─── Market ──────────────────────────────────────────────
  search: (query: string, signal?: AbortSignal) =>
    request<SymbolMatch[]>(`/api/market/search${q({ q: query, limit: 8 })}`, { signal, timeoutMs: 15_000 }),
  quotes: (symbols: string[]) => request<QuoteResult[]>(`/api/market/quotes${q({ symbols: symbols.join(',') })}`),
  quote: (symbol: string) => request<Quote>(`/api/market/${seg(symbol)}/quote`),
  profile: (symbol: string) => request<Profile>(`/api/market/${seg(symbol)}/profile`),
  history: (symbol: string, period: string) => request<History>(`/api/market/${seg(symbol)}/history${q({ period })}`),
  technicals: (symbol: string, period: string) =>
    request<Technicals>(`/api/market/${seg(symbol)}/technicals${q({ period })}`),
  news: (symbol: string, limit = 12) => request<NewsFeed>(`/api/market/${seg(symbol)}/news${q({ limit })}`),
  analyzeAsset: (body: { symbol: string; benchmark?: string; period?: string; risk_free_rate?: number }) =>
    request<AssetAnalysis>('/api/analytics/asset', { body, timeoutMs: 60_000 }),

  // ─── Portfolio ───────────────────────────────────────────
  analyzePortfolio: (body: {
    holdings: HoldingInput[];
    model: RebalancingModel;
    benchmark?: string;
    period?: string;
    risk_free_rate?: number;
  }) => request<PortfolioAnalysis>('/api/portfolio/analyze', { body, timeoutMs: 90_000 }),
  stressPortfolio: (body: { holdings: HoldingInput[]; benchmark?: string }) =>
    request<StressResult>('/api/portfolio/stress', { body, timeoutMs: 90_000 }),
  listPortfolios: () => request<{ items: SavedPortfolio[]; page: PageMeta }>('/api/portfolios?limit=100'),
  createPortfolio: (body: Omit<SavedPortfolio, 'id' | 'version' | 'created_at' | 'updated_at'>) =>
    request<SavedPortfolio>('/api/portfolios', { body }),
  updatePortfolio: (id: string, body: Omit<SavedPortfolio, 'id' | 'created_at' | 'updated_at'>) =>
    request<SavedPortfolio>(`/api/portfolios/${seg(id)}`, { method: 'PUT', body }),
  deletePortfolio: (id: string) => request<void>(`/api/portfolios/${seg(id)}`, { method: 'DELETE' }),

  // ─── Auth ────────────────────────────────────────────────
  me: () => request<User>('/api/auth/me'),
  login: (email: string, password: string) => request<SessionInfo>('/api/auth/login', { body: { email, password } }),
  signup: (email: string, password: string, display_name?: string) =>
    request<SessionInfo>('/api/auth/signup', { body: { email, password, display_name: display_name || null } }),
  logout: () => request<void>('/api/auth/logout', { method: 'POST' }),

  // ─── Watchlist ───────────────────────────────────────────
  watchlist: () => request<WatchlistItem[]>('/api/watchlist'),
  watch: (symbol: string) => request<WatchlistItem>('/api/watchlist', { body: { symbol } }),
  unwatch: (symbol: string) => request<void>(`/api/watchlist/${seg(symbol)}`, { method: 'DELETE' }),

  // ─── Research ────────────────────────────────────────────
  research: (body: { symbol: string; question?: string; period?: string; save?: boolean }) =>
    request<ResearchReport>('/api/research', { body, timeoutMs: 180_000 }),
  researchHistory: (symbol?: string, limit = 30, offset = 0) =>
    request<{ items: ResearchSummary[]; page: PageMeta }>(`/api/research${q({ symbol, limit, offset })}`),
  researchReport: (id: string) => request<ResearchReport>(`/api/research/${seg(id)}`),
  deleteResearch: (id: string) => request<void>(`/api/research/${seg(id)}`, { method: 'DELETE' }),

  // ─── Documents ───────────────────────────────────────────
  documents: (symbol?: string) =>
    request<{ items: DocumentRecord[]; page: PageMeta }>(`/api/documents${q({ symbol, limit: 100 })}`),
  uploadDocument: (input: {
    file: File;
    symbol: string;
    document_type: DocumentType;
    title?: string;
    source_url?: string;
    published_on?: string;
  }) => {
    const form = new FormData();
    form.set('file', input.file);
    form.set('symbol', input.symbol);
    form.set('document_type', input.document_type);
    if (input.title) form.set('title', input.title);
    if (input.source_url) form.set('source_url', input.source_url);
    if (input.published_on) form.set('published_on', input.published_on);
    return request<DocumentRecord>('/api/documents', { form, method: 'POST', timeoutMs: 300_000 });
  },
  deleteDocument: (id: string) => request<void>(`/api/documents/${seg(id)}`, { method: 'DELETE' }),
  searchDocuments: (body: { query: string; symbol?: string; limit?: number }) =>
    request<{ query: string; passages: Passage[]; insufficient_evidence: boolean }>('/api/documents/search', {
      body,
      timeoutMs: 60_000,
    }),
  filings: (symbol: string, limit = 20) => request<Filing[]>(`/api/filings/${seg(symbol)}${q({ limit })}`),
  importFiling: (symbol: string, accession: string) =>
    request<DocumentRecord>('/api/documents/import-sec', { body: { symbol, accession }, timeoutMs: 300_000 }),
  documentFileUrl: (id: string, page?: number | null) =>
    `${getApiBase()}/api/documents/${seg(id)}/file${page ? `#page=${page}` : ''}`,
};

// ─── Streaming research ──────────────────────────────────────

export interface ResearchStreamHandlers {
  onStep: (step: ResearchStep) => void;
  signal?: AbortSignal;
}

/** POST /api/research/stream and resolve with the final report. */
export async function streamResearch(
  body: { symbol: string; question?: string; period?: string; save?: boolean },
  handlers: ResearchStreamHandlers,
): Promise<ResearchReport> {
  let response: Response;
  try {
    response = await fetch(`${getApiBase()}/api/research/stream`, {
      method: 'POST',
      credentials: 'include',
      headers: { ...buildHeaders('POST', true), Accept: 'text/event-stream' },
      body: JSON.stringify(body),
      signal: handlers.signal,
      cache: 'no-store',
    });
  } catch {
    if (handlers.signal?.aborted) throw new ApiError('Research cancelled.', 0, 'cancelled');
    throw new ApiError('Cannot reach the ARGUS backend.', 0, 'network_error');
  }
  const requestId = response.headers.get('x-request-id');
  if (!response.ok || !response.body) {
    const text = await response.text().catch(() => '');
    let parsed: unknown = null;
    try {
      parsed = text ? JSON.parse(text) : null;
    } catch {
      parsed = null;
    }
    const retry = Number(response.headers.get('retry-after'));
    throw errorFromBody(response.status, parsed, requestId, Number.isFinite(retry) && retry > 0 ? retry : null);
  }

  let report: ResearchReport | null = null;
  let failure: ApiError | null = null;
  try {
    for await (const event of readEventStream(response.body)) {
      let data: unknown;
      try {
        data = JSON.parse(event.data);
      } catch {
        continue;
      }
      if (event.event === 'step') handlers.onStep(data as ResearchStep);
      else if (event.event === 'report') report = data as ResearchReport;
      else if (event.event === 'error') failure = errorFromBody(500, data, requestId, null);
    }
  } catch {
    if (handlers.signal?.aborted) throw new ApiError('Research cancelled.', 0, 'cancelled');
    throw new ApiError('The research stream was interrupted.', 0, 'stream_interrupted', requestId);
  }
  if (failure) throw failure;
  if (!report) throw new ApiError('The research stream ended without a report.', 0, 'stream_incomplete', requestId);
  return report;
}
