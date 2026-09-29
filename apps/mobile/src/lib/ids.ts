/** Random id for anonymous analytics / AI sessions (not a secret). */
export function randomId(bytes = 16): string {
  const out: string[] = [];
  const cryptoObj = (globalThis as { crypto?: { getRandomValues?: (a: Uint8Array) => Uint8Array } }).crypto;
  const buf = new Uint8Array(bytes);
  if (cryptoObj?.getRandomValues) cryptoObj.getRandomValues(buf);
  else for (let i = 0; i < bytes; i++) buf[i] = Math.floor(Math.random() * 256);
  for (const b of buf) out.push(b.toString(16).padStart(2, '0'));
  return out.join('');
}
