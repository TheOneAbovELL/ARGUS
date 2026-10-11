import { describe, expect, it } from 'vitest';
import { parseSseChunk, readEventStream } from '@/lib/sse';

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

describe('parseSseChunk', () => {
  it('parses complete frames and keeps the incomplete tail', () => {
    const { events, rest } = parseSseChunk('event: step\ndata: {"a":1}\n\nevent: report\ndata: {"b"');
    expect(events).toEqual([{ event: 'step', data: '{"a":1}' }]);
    expect(rest).toBe('event: report\ndata: {"b"');
  });

  it('handles CRLF, comments, default event names and multi-line data', () => {
    const { events } = parseSseChunk(': keep-alive\r\n\r\ndata: line1\r\ndata: line2\r\n\r\n');
    expect(events).toEqual([{ event: 'message', data: 'line1\nline2' }]);
  });
});

describe('readEventStream', () => {
  it('reassembles events split across network chunks', async () => {
    const body = streamOf(['event: st', 'ep\ndata: {"step":"market_data"}\n', '\nevent: report\ndata: {"symbol":"NVDA"}\n\n']);
    const events = [];
    for await (const event of readEventStream(body)) events.push(event);
    expect(events).toEqual([
      { event: 'step', data: '{"step":"market_data"}' },
      { event: 'report', data: '{"symbol":"NVDA"}' },
    ]);
  });

  it('flushes a final frame without a trailing blank line', async () => {
    const events = [];
    for await (const event of readEventStream(streamOf(['event: error\ndata: {"x":1}']))) events.push(event);
    expect(events).toEqual([{ event: 'error', data: '{"x":1}' }]);
  });
});
