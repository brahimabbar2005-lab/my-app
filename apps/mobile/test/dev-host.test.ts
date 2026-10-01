import { describe, expect, it } from 'vitest';

import { devHostUrl } from '../src/lib/dev-host';

describe('devHostUrl', () => {
  it('points localhost services at the computer Expo Go loaded the app from', () => {
    expect(devHostUrl('http://localhost:8000', '192.168.1.20:8081', 'android')).toBe('http://192.168.1.20:8000');
    expect(devHostUrl('http://127.0.0.1:8787/v1', 'macbook.local:8081', 'ios')).toBe('http://macbook.local:8787/v1');
  });

  it('leaves the web, tunnels and real servers alone', () => {
    expect(devHostUrl('http://localhost:8000', '192.168.1.20:8081', 'web')).toBe('http://localhost:8000');
    expect(devHostUrl('http://localhost:8000', 'abc-anonymous-8081.exp.direct', 'ios')).toBe('http://localhost:8000');
    expect(devHostUrl('https://ai.comemorocco.com', '192.168.1.20:8081', 'ios')).toBe('https://ai.comemorocco.com');
    expect(devHostUrl('http://localhost:8000', null, 'ios')).toBe('http://localhost:8000');
    expect(devHostUrl('http://localhost.evil.com', '192.168.1.20:8081', 'ios')).toBe('http://localhost.evil.com');
  });
});
