import { describe, expect, it, vi } from 'vitest';

import type { ChatStreamEvent } from '../src/api/v1/chat';
import { streamChat } from '../src/client/ai';
import { SseParser } from '../src/client/sse';

const meta = { session_id: 's', conversation_id: 'c', resources: [], affiliates: [], notices: [], intents: [], language: 'en' };
const done = { conversation_id: 'c', message_id: 'm', latency_ms: 5, trip_state: {} };

function sseBody(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c));
      controller.close();
    },
  });
}

describe('SseParser', () => {
  it('handles CRLF, comments, multi-line data and a missing final blank line', () => {
    const p = new SseParser();
    const out = [
      ...p.feed(': keep-alive\r\n\r\nevent: delta\r\ndata: {"text":'),
      ...p.feed('"a"}\r\n\r\ndata: line1\ndata: line2\n\nevent: done\ndata: {}'),
      ...p.flush(),
    ];
    expect(out).toEqual([
      { event: 'delta', data: '{"text":"a"}' },
      { event: 'message', data: 'line1\nline2' },
      { event: 'done', data: '{}' },
    ]);
  });
});

describe('streamChat', () => {
  it('streams meta → delta → done and sends the app key and bearer token', async () => {
    const body = sseBody([
      `event: meta\ndata: ${JSON.stringify(meta)}\n\n`,
      'event: delta\ndata: {"text":"Fes "}\n\nevent: del',
      'ta\ndata: {"text":"first."}\n\n',
      `event: done\ndata: ${JSON.stringify(done)}\n\n`,
    ]);
    const fetch = vi.fn(async () => new Response(body, { status: 200 }));
    const events: ChatStreamEvent[] = [];
    const transport = await streamChat(
      { baseUrl: 'http://ai.test/', appKey: 'k', getAccessToken: () => 'tok', fetch },
      { message: 'Marrakech or Fes?' },
      (e) => events.push(e),
    );
    expect(transport).toBe('stream');
    expect(events.map((e) => e.type)).toEqual(['meta', 'delta', 'delta', 'done']);
    const text = events.flatMap((e) => (e.type === 'delta' ? [e.data.text] : [])).join('');
    expect(text).toBe('Fes first.');
    const [calledUrl, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(calledUrl).toBe('http://ai.test/api/chat/stream');
    const headers = init.headers as Record<string, string>;
    expect(headers['X-App-Key']).toBe('k');
    expect(headers.Authorization).toBe('Bearer tok');
  });

  it('falls back to the JSON endpoint when the body cannot be read incrementally', async () => {
    const jsonBody = { ...meta, message_id: 'm', answer: 'Hello', trip_state: {}, latency_ms: 3 };
    const fetch = vi.fn(async (url: string) => {
      if (url.endsWith('/stream')) {
        // A runtime without streaming: a Response-like object with no body reader.
        return { ok: true, status: 200, body: null } as unknown as Response;
      }
      return new Response(JSON.stringify(jsonBody), { status: 200 });
    });
    const events: ChatStreamEvent[] = [];
    const transport = await streamChat({ baseUrl: 'http://ai.test', fetch }, { message: 'hi' }, (e) => events.push(e));
    expect(transport).toBe('json');
    expect(events.map((e) => e.type)).toEqual(['meta', 'delta', 'done']);
  });

  it('turns a 429 into an error event carrying the service answer', async () => {
    const fetch = vi.fn(
      async () => new Response(JSON.stringify({ error: 'too_fast', answer: 'Slow down a little.' }), { status: 429 }),
    );
    const events: ChatStreamEvent[] = [];
    await streamChat({ baseUrl: 'http://ai.test', fetch }, { message: 'hi' }, (e) => events.push(e));
    expect(events).toEqual([{ type: 'error', data: { answer: 'Slow down a little.' } }]);
  });

  it('turns a network failure into an error event', async () => {
    const fetch = vi.fn(async () => {
      throw new TypeError('network down');
    });
    const events: ChatStreamEvent[] = [];
    await streamChat({ baseUrl: 'http://ai.test', fetch }, { message: 'hi' }, (e) => events.push(e));
    expect(events[0]?.type).toBe('error');
  });

  it('rejects an empty message before any request', async () => {
    const fetch = vi.fn();
    await expect(streamChat({ baseUrl: 'http://ai.test', fetch }, { message: '   ' }, () => {})).rejects.toThrow();
    expect(fetch).not.toHaveBeenCalled();
  });
});
