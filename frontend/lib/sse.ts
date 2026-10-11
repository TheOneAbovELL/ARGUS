// Minimal Server-Sent Events parser for fetch() response bodies.
// EventSource cannot POST, so research streaming reads the body directly.

export interface SseEvent {
  event: string;
  data: string;
}

/** Parse complete SSE frames out of `buffer`; return events and the unparsed tail. */
export function parseSseChunk(buffer: string): { events: SseEvent[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, '\n');
  const frames = normalized.split('\n\n');
  const rest = frames.pop() ?? '';
  const events: SseEvent[] = [];
  for (const frame of frames) {
    let event = 'message';
    const data: string[] = [];
    for (const line of frame.split('\n')) {
      if (!line || line.startsWith(':')) continue;
      const colon = line.indexOf(':');
      const field = colon === -1 ? line : line.slice(0, colon);
      const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '');
      if (field === 'event') event = value;
      else if (field === 'data') data.push(value);
    }
    if (data.length) events.push({ event, data: data.join('\n') });
  }
  return { events, rest };
}

export async function* readEventStream(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const { events, rest } = parseSseChunk(buffer);
      buffer = rest;
      for (const event of events) yield event;
    }
    buffer += decoder.decode();
    const { events } = parseSseChunk(buffer + '\n\n');
    for (const event of events) yield event;
  } finally {
    reader.releaseLock();
  }
}
