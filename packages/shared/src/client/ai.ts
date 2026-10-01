/**
 * Client for the ComeMorocco AI service.
 *
 * `streamChat` uses POST /api/chat/stream (SSE) when the runtime's fetch can
 * read a response body incrementally, and falls back to POST /api/chat (JSON)
 * otherwise, emitting the same meta → delta → done events either way. The UI
 * never needs to know which transport was used (Master Plan §52F).
 *
 * In the Expo app, pass `fetch` from 'expo/fetch', which supports streaming.
 */
import {
  ChatError,
  ChatRequest,
  ChatResponse,
  type ChatStreamEvent,
  StreamDelta,
  StreamDone,
  StreamError,
  StreamMeta,
} from '../api/v1/chat';
import { SseParser } from './sse';

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export interface AiClientOptions {
  baseUrl: string;
  /** Sent as X-App-Key. Abuse friction, not a secret. */
  appKey?: string;
  /** Supabase access token for signed-in users (higher AI limits). */
  getAccessToken?: () => string | null | undefined | Promise<string | null | undefined>;
  fetch?: FetchLike;
}

export type Transport = 'stream' | 'json';

const FALLBACK_ANSWER =
  "Sorry — I can't reach the ComeMorocco AI right now. Please try again in a moment.";

async function headers(opts: AiClientOptions, accept: string): Promise<Record<string, string>> {
  const out: Record<string, string> = { 'Content-Type': 'application/json', Accept: accept };
  if (opts.appKey) out['X-App-Key'] = opts.appKey;
  const token = await opts.getAccessToken?.();
  if (token) out.Authorization = `Bearer ${token}`;
  return out;
}

function url(opts: AiClientOptions, path: string): string {
  return opts.baseUrl.replace(/\/+$/, '') + path;
}

async function errorAnswer(response: Response): Promise<string> {
  try {
    const body = ChatError.safeParse(await response.json());
    if (body.success && body.data.answer) return body.data.answer;
  } catch {
    // fall through
  }
  return FALLBACK_ANSWER;
}

function toEvent(event: string, raw: string): ChatStreamEvent | null {
  let json: unknown;
  try {
    json = JSON.parse(raw);
  } catch {
    return null;
  }
  switch (event) {
    case 'meta': {
      const r = StreamMeta.safeParse(json);
      return r.success ? { type: 'meta', data: r.data } : null;
    }
    case 'delta': {
      const r = StreamDelta.safeParse(json);
      return r.success ? { type: 'delta', data: r.data } : null;
    }
    case 'done': {
      const r = StreamDone.safeParse(json);
      return r.success ? { type: 'done', data: r.data } : null;
    }
    case 'error': {
      const r = StreamError.safeParse(json);
      return { type: 'error', data: r.success ? r.data : { answer: FALLBACK_ANSWER } };
    }
    default:
      return null;
  }
}

/** Non-streaming request; also the fallback transport. */
export async function sendChat(
  opts: AiClientOptions,
  request: ChatRequest,
  signal?: AbortSignal,
): Promise<ChatResponse | { error: string; answer: string }> {
  const doFetch = opts.fetch ?? (globalThis.fetch as FetchLike);
  const body = ChatRequest.parse(request);
  let response: Response;
  try {
    response = await doFetch(url(opts, '/api/chat'), {
      method: 'POST',
      headers: await headers(opts, 'application/json'),
      body: JSON.stringify(body),
      signal,
    });
  } catch {
    return { error: 'network', answer: FALLBACK_ANSWER };
  }
  if (!response.ok) return { error: `http_${response.status}`, answer: await errorAnswer(response) };
  const parsed = ChatResponse.safeParse(await response.json());
  return parsed.success ? parsed.data : { error: 'bad_response', answer: FALLBACK_ANSWER };
}

export async function streamChat(
  opts: AiClientOptions,
  request: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<Transport> {
  const doFetch = opts.fetch ?? (globalThis.fetch as FetchLike);
  const body = ChatRequest.parse(request);

  let response: Response;
  try {
    response = await doFetch(url(opts, '/api/chat/stream'), {
      method: 'POST',
      headers: await headers(opts, 'text/event-stream'),
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (signal?.aborted) throw err;
    const reason = err instanceof Error ? err.message : String(err);
    onEvent({ type: 'error', data: { answer: FALLBACK_ANSWER, detail: `${opts.baseUrl}: ${reason}` } });
    return 'stream';
  }

  if (!response.ok) {
    onEvent({
      type: 'error',
      data: { answer: await errorAnswer(response), detail: `${opts.baseUrl}: HTTP ${response.status}` },
    });
    return 'stream';
  }

  const reader = response.body?.getReader?.();
  if (!reader) {
    // This runtime cannot stream: repeat the request on the JSON endpoint.
    await jsonAsEvents(opts, body, onEvent, signal);
    return 'json';
  }

  const decoder = new TextDecoder();
  const parser = new SseParser();
  const emit = (messages: { event: string; data: string }[]) => {
    for (const m of messages) {
      const event = toEvent(m.event, m.data);
      if (event) onEvent(event);
    }
  };
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    emit(parser.feed(decoder.decode(value, { stream: true })));
  }
  emit(parser.feed(decoder.decode()));
  emit(parser.flush());
  return 'stream';
}

async function jsonAsEvents(
  opts: AiClientOptions,
  body: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const result = await sendChat(opts, body, signal);
  if ('error' in result) {
    onEvent({ type: 'error', data: { answer: result.answer } });
    return;
  }
  onEvent({
    type: 'meta',
    data: {
      session_id: result.session_id,
      conversation_id: result.conversation_id,
      resources: result.resources,
      affiliates: result.affiliates,
      notices: result.notices,
      actions: result.actions,
      intents: result.intents,
      language: result.language,
      trip_state: result.trip_state,
    },
  });
  onEvent({ type: 'delta', data: { text: result.answer } });
  onEvent({
    type: 'done',
    data: {
      conversation_id: result.conversation_id,
      message_id: result.message_id,
      latency_ms: result.latency_ms,
      trip_state: result.trip_state,
    },
  });
}

export async function getStarters(opts: AiClientOptions, lang: string): Promise<string[]> {
  const doFetch = opts.fetch ?? (globalThis.fetch as FetchLike);
  try {
    const response = await doFetch(url(opts, `/api/starters?lang=${encodeURIComponent(lang)}`), {
      headers: await headers(opts, 'application/json'),
    });
    if (!response.ok) return [];
    const data = (await response.json()) as { starters?: unknown };
    return Array.isArray(data.starters) ? data.starters.filter((s): s is string => typeof s === 'string') : [];
  } catch {
    return [];
  }
}

export async function sendFeedback(
  opts: AiClientOptions,
  feedback: { message_id: string; helpful: boolean; reason?: string | null },
): Promise<boolean> {
  const doFetch = opts.fetch ?? (globalThis.fetch as FetchLike);
  try {
    const response = await doFetch(url(opts, '/api/feedback'), {
      method: 'POST',
      headers: await headers(opts, 'application/json'),
      body: JSON.stringify(feedback),
    });
    return response.ok;
  } catch {
    return false;
  }
}
