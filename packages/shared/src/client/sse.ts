/**
 * Incremental server-sent-events parser.
 *
 * Fed arbitrary text chunks (network boundaries fall anywhere, including in
 * the middle of a line or a multi-byte character — decoding is the caller's
 * job via TextDecoder with {stream: true}). Emits one event per blank-line
 * terminated block.
 */
export interface SseMessage {
  event: string;
  data: string;
}

export class SseParser {
  private buffer = '';

  feed(chunk: string): SseMessage[] {
    this.buffer += chunk.replace(/\r\n?/g, '\n');
    const out: SseMessage[] = [];
    let boundary = this.buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const block = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      const message = parseBlock(block);
      if (message) out.push(message);
      boundary = this.buffer.indexOf('\n\n');
    }
    return out;
  }

  /** Whatever is left when the stream closes without a final blank line. */
  flush(): SseMessage[] {
    const rest = this.buffer;
    this.buffer = '';
    const message = rest.trim() ? parseBlock(rest) : null;
    return message ? [message] : [];
  }
}

function parseBlock(block: string): SseMessage | null {
  let event = 'message';
  const data: string[] = [];
  for (const line of block.split('\n')) {
    if (!line || line.startsWith(':')) continue;
    const colon = line.indexOf(':');
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? '' : line.slice(colon + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'event') event = value;
    else if (field === 'data') data.push(value);
  }
  return data.length ? { event, data: data.join('\n') } : null;
}
