import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { authorizeToolCall } from '../src/api/v1/actions';
import { ChatResponse, StreamDone, StreamMeta } from '../src/api/v1/chat';
import { SseParser } from '../src/client/sse';

const examples = join(__dirname, '..', 'contracts', 'v1', 'examples');
const read = (name: string) => readFileSync(join(examples, name), 'utf8');

describe('v1 contract — payloads produced by services/ai', () => {
  it.each(['chat_response.commercial.json', 'chat_response.advice.json'])('%s parses as ChatResponse', (name) => {
    const payload = JSON.parse(read(name));
    const parsed = ChatResponse.parse(payload);
    expect(parsed.answer.length).toBeGreaterThan(0);
    // No field the service sends is silently dropped by the schema.
    expect(Object.keys(parsed).sort()).toEqual(Object.keys(payload).sort());
  });

  it('the stream example parses event by event', () => {
    const parser = new SseParser();
    const text = read('chat_stream.commercial.sse');
    // Feed in awkward 7-character chunks to exercise split lines.
    const messages = [];
    for (let i = 0; i < text.length; i += 7) messages.push(...parser.feed(text.slice(i, i + 7)));
    messages.push(...parser.flush());

    expect(messages[0]?.event).toBe('meta');
    expect(messages.at(-1)?.event).toBe('done');
    const meta = StreamMeta.parse(JSON.parse(messages[0]!.data));
    expect(meta.affiliates.length).toBeGreaterThan(0);
    expect(meta.resources[0]?.url).toMatch(/^https:\/\/comemorocco\.com\//);
    StreamDone.parse(JSON.parse(messages.at(-1)!.data));
  });

  it('every action the service proposes passes the app\'s action validator', () => {
    const text = read('chat_stream.commercial.sse');
    const meta = StreamMeta.parse(JSON.parse(new SseParser().feed(text)[0]!.data));
    expect(meta.actions.length).toBeGreaterThan(0);
    for (const action of meta.actions) {
      const tapped = authorizeToolCall(action.tool, action.args, { signedIn: true, userRequested: true });
      expect(tapped.outcome, `${action.id}`).toBe('execute');
      // Never runs on its own: a write needs the traveller's request.
      expect(authorizeToolCall(action.tool, action.args, { signedIn: true, userRequested: false }).outcome).toBe('rejected');
    }
  });
});
