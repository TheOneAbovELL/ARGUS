import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, describeError, errorFromBody, request, streamResearch } from '@/lib/api';

type FetchArgs = [string, RequestInit];

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'x-request-id': 'req-123', ...headers },
  });
}

let fetchMock: ReturnType<typeof vi.fn>;

/** Await a promise that must reject with an ApiError and return that error. */
async function rejection(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    expect(error).toBeInstanceOf(ApiError);
    return error as ApiError;
  }
  throw new Error('expected the promise to reject');
}

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('request', () => {
  it('sends credentials and no CSRF header on GET', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { status: 'ok' }));
    await request('/api/system/status');
    const [url, init] = fetchMock.mock.calls[0] as FetchArgs;
    expect(url).toBe('http://localhost:8000/api/system/status');
    expect(init.credentials).toBe('include');
    expect(init.method).toBe('GET');
    expect((init.headers as Record<string, string>)['X-ARGUS-CSRF']).toBeUndefined();
  });

  it('adds the CSRF header and JSON body on mutating requests', async () => {
    fetchMock.mockResolvedValue(jsonResponse(201, { symbol: 'NVDA', created_at: 'x' }));
    await api.watch('NVDA');
    const [, init] = fetchMock.mock.calls[0] as FetchArgs;
    expect(init.method).toBe('POST');
    expect((init.headers as Record<string, string>)['X-ARGUS-CSRF']).toBe('1');
    expect(JSON.parse(init.body as string)).toEqual({ symbol: 'NVDA' });
  });

  it('sends CSRF on DELETE and handles 204 No Content', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(api.unwatch('BRK-B')).resolves.toBeUndefined();
    const [url, init] = fetchMock.mock.calls[0] as FetchArgs;
    expect(url).toContain('/api/watchlist/BRK-B');
    expect((init.headers as Record<string, string>)['X-ARGUS-CSRF']).toBe('1');
  });

  it('URL-encodes symbols in paths', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}));
    await api.quote('^GSPC');
    expect((fetchMock.mock.calls[0] as FetchArgs)[0]).toContain('/api/market/%5EGSPC/quote');
  });

  it('parses the error envelope into a typed ApiError', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(422, { error: { code: 'insufficient_data', message: 'Not enough history.' }, request_id: 'abc' }),
    );
    const error = await rejection(request('/api/analytics/asset', { body: {} }));
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(422);
    expect(error.code).toBe('insufficient_data');
    expect(error.message).toBe('Not enough history.');
    expect(error.requestId).toBe('abc');
  });

  it('exposes Retry-After on rate limiting', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(429, { error: { code: 'rate_limited', message: 'Slow down.' }, request_id: 'r' }, { 'retry-after': '17' }),
    );
    const error = await rejection(request('/api/research', { body: {} }));
    expect(error.retryAfter).toBe(17);
    expect(describeError(error)).toBe('Slow down. Retry in 17s.');
  });

  it('turns network failures into an actionable error instead of a fake success', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    const error = await rejection(request('/api/system/status'));
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe('network_error');
  });

  it('falls back to a generic message for non-envelope errors', () => {
    const error = errorFromBody(502, '<html>bad gateway</html>', 'rid', null);
    expect(error.code).toBe('http_error');
    expect(error.message).toMatch(/server/i);
    expect(error.requestId).toBe('rid');
  });
});

describe('streamResearch', () => {
  function sse(frames: string): Response {
    return new Response(new TextEncoder().encode(frames), { status: 200, headers: { 'content-type': 'text/event-stream' } });
  }

  it('reports steps and resolves with the final report', async () => {
    fetchMock.mockResolvedValue(
      sse(
        'event: step\ndata: {"type":"step","step":"market_data","status":"ok","detail":null}\n\n' +
          'event: report\ndata: {"symbol":"NVDA","sections":[]}\n\n',
      ),
    );
    const steps: string[] = [];
    const report = await streamResearch({ symbol: 'NVDA' }, { onStep: (s) => steps.push(s.step) });
    expect(steps).toEqual(['market_data']);
    expect(report.symbol).toBe('NVDA');
    const [, init] = fetchMock.mock.calls[0] as FetchArgs;
    expect((init.headers as Record<string, string>)['X-ARGUS-CSRF']).toBe('1');
  });

  it('surfaces a streamed error event as an ApiError', async () => {
    fetchMock.mockResolvedValue(sse('event: error\ndata: {"error":{"code":"symbol_not_found","message":"No data."},"request_id":"x"}\n\n'));
    const error = await rejection(streamResearch({ symbol: 'ZZZZ' }, { onStep: () => {} }));
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe('symbol_not_found');
  });

  it('fails explicitly when the stream ends without a report', async () => {
    fetchMock.mockResolvedValue(sse('event: step\ndata: {"type":"step","step":"market_data","status":"running","detail":null}\n\n'));
    const error = await rejection(streamResearch({ symbol: 'NVDA' }, { onStep: () => {} }));
    expect(error.code).toBe('stream_incomplete');
  });

  it('returns HTTP errors before streaming starts', async () => {
    fetchMock.mockResolvedValue(jsonResponse(400, { error: { code: 'invalid_request', message: 'Bad symbol.' }, request_id: 'q' }));
    const error = await rejection(streamResearch({ symbol: '!!' }, { onStep: () => {} }));
    expect(error.status).toBe(400);
    expect(error.message).toBe('Bad symbol.');
  });
});
