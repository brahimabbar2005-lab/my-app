import { describe, expect, it, vi } from 'vitest';

import { networkFor, withSubId } from '../src/affiliates';
import { plainText } from '../src/content';
import { createApp, type Env } from '../src/index';

const baseEnv: Env = {
  SITE_URL: 'https://comemorocco.com',
  WORDPRESS_URL: 'https://comemorocco.com',
  ALLOWED_ORIGINS: 'http://localhost:8081',
};
const CLICK_ID = '11111111-2222-3333-4444-555555555555';

function setup(env: Partial<Env> = {}, fetchImpl?: (url: string, init?: RequestInit) => Promise<Response>) {
  const fetchMock = vi.fn(fetchImpl ?? (async () => new Response('[]', { status: 200 })));
  const app = createApp({ fetch: fetchMock as unknown as typeof fetch, uuid: () => CLICK_ID });
  const request = (path: string, init?: RequestInit) => app.request(path, init, { ...baseEnv, ...env });
  return { request, fetchMock };
}

describe('/go/:listingId', () => {
  it('redirects a known listing to its partner with the click id as sub-id', async () => {
    const { request } = setup();
    const res = await request('/go/AFF-013?src=book&platform=ios&aid=abcdef0123456789');
    expect(res.status).toBe(302);
    const location = new URL(res.headers.get('location')!);
    expect(location.hostname).toBe('booking.tpx.li');
    expect(location.searchParams.get('sub_id')).toBe(CLICK_ID);
    expect(res.headers.get('cache-control')).toBe('no-store');
  });

  it('resolves AI affiliate ids (GetYourGuide activities) too', async () => {
    const { request } = setup();
    const res = await request('/go/GYG-008?src=ai');
    expect(new URL(res.headers.get('location')!).hostname).toBe('gyg.me');
  });

  it('never redirects anywhere but the site for unknown or malformed ids (no open redirect)', async () => {
    const { request } = setup();
    for (const path of ['/go/NOPE-999', '/go/..%2Fadmin', '/go/https%3A%2F%2Fevil.example']) {
      const res = await request(path);
      expect(res.status).toBe(302);
      expect(res.headers.get('location')).toBe('https://comemorocco.com');
    }
  });

  it('logs the click to the console without Supabase', async () => {
    const log = vi.spyOn(console, 'log').mockImplementation(() => {});
    const { request } = setup();
    await request('/go/AFF-021?src=explore&cmp=spring');
    const line = JSON.parse(log.mock.calls.at(-1)![0] as string);
    expect(line).toMatchObject({ event: 'affiliate_click', id: CLICK_ID, listing_id: 'AFF-021', source: 'explore', campaign: 'spring' });
    log.mockRestore();
  });

  it('with Supabase: resolves from affiliate_links and inserts into affiliate_clicks', async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    const { request } = setup(
      { SUPABASE_URL: 'https://proj.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'service-key' },
      async (url, init) => {
        calls.push({ url, init });
        if (url.includes('/rest/v1/affiliate_links')) {
          return new Response(JSON.stringify([{ url: 'https://gyg.me/xyz', partner: 'getyourguide', program_id: null }]));
        }
        return new Response(null, { status: 201 });
      },
    );
    const res = await request('/go/LISTING-1?src=ai');
    expect(new URL(res.headers.get('location')!).searchParams.get('cmp')).toBe(CLICK_ID);
    expect(calls[0]!.url).toContain('listing_id=eq.LISTING-1');
    const insert = calls.find((c) => c.url.endsWith('/rest/v1/affiliate_clicks'))!;
    expect(insert.init?.method).toBe('POST');
    expect(JSON.parse(insert.init!.body as string)).toMatchObject({ id: CLICK_ID, listing_id: 'LISTING-1', source: 'ai' });
    expect((insert.init!.headers as Record<string, string>).Authorization).toBe('Bearer service-key');
  });

  it('falls back to the generated map when Supabase is down, and still redirects if logging fails', async () => {
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { request } = setup(
      { SUPABASE_URL: 'https://proj.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'k' },
      async () => new Response('down', { status: 503 }),
    );
    const res = await request('/go/AFF-013');
    expect(new URL(res.headers.get('location')!).hostname).toBe('booking.tpx.li');
    expect(err).toHaveBeenCalled();
    err.mockRestore();
  });

  it('ignores invalid tracking parameters instead of failing', async () => {
    const { request } = setup();
    const res = await request('/go/AFF-013?src=not-a-source&aid=x');
    expect(res.status).toBe(302);
    expect(new URL(res.headers.get('location')!).hostname).toBe('booking.tpx.li');
  });
});

describe('/v1/content', () => {
  const post = {
    id: 4079,
    link: 'https://comemorocco.com/best-sahara-desert-tour/',
    modified_gmt: '2026-09-01T10:00:00',
    title: { rendered: 'Best Sahara Desert Tour &#8211; 2026' },
    excerpt: { rendered: '<p>Dunes, camps &amp; camels.</p>' },
    _embedded: { 'wp:featuredmedia': [{ source_url: 'https://comemorocco.com/wp-content/uploads/sahara.jpg' }] },
  };

  it('maps WordPress posts to content references with canonical URLs', async () => {
    const { request, fetchMock } = setup({}, async () =>
      new Response(JSON.stringify([post, { id: 2, link: 'https://evil.example/x' }])),
    );
    const res = await request('/v1/content?destination=merzouga&limit=5', { headers: { Origin: 'http://localhost:8081' } });
    const body = (await res.json()) as { items: { title: string; excerpt: string; image_url: string }[]; source: string };
    expect(body.source).toBe('live');
    expect(body.items).toHaveLength(1);
    expect(body.items[0]).toMatchObject({ title: 'Best Sahara Desert Tour – 2026', excerpt: 'Dunes, camps & camels.' });
    expect(res.headers.get('access-control-allow-origin')).toBe('http://localhost:8081');
    const called = new URL(fetchMock.mock.calls[0]![0] as string);
    expect(called.pathname).toBe('/wp-json/wp/v2/posts');
    expect(called.searchParams.get('search')).toBe('merzouga');
  });

  it('returns an empty fallback when WordPress is unreachable', async () => {
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { request } = setup({}, async () => {
      throw new TypeError('network');
    });
    const body = await (await request('/v1/content')).json();
    expect(body).toEqual({ items: [], source: 'fallback' });
    err.mockRestore();
  });
});

describe('helpers', () => {
  it('identifies networks and adds sub-ids without touching host or path', () => {
    expect(networkFor('https://booking.tpx.li/Xk')).toBe('travelpayouts');
    expect(networkFor('https://gyg.me/abc')).toBe('getyourguide');
    expect(withSubId('https://example.com/p?a=1', 'c1')).toBe('https://example.com/p?a=1');
    expect(withSubId('https://booking.tpx.li/Xk?x=1', 'c1')).toBe('https://booking.tpx.li/Xk?x=1&sub_id=c1');
  });

  it('turns WordPress HTML into plain text', () => {
    expect(plainText('<p>Fes &amp; Meknes&hellip;</p>')).toBe('Fes & Meknes…');
  });

  it('health reports whether Supabase is configured', async () => {
    const { request } = setup();
    expect(await (await request('/health')).json()).toEqual({ status: 'ok', supabase: false });
  });
});
