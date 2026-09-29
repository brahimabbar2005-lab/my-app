/**
 * ComeMorocco platform worker.
 *
 *   GET /health
 *   GET /go/:listingId      affiliate click → partner redirect
 *   GET /v1/content         ComeMorocco articles from WordPress (cached)
 *
 * Kept deliberately light (Workers Free: 10 ms CPU): lookups, redirects and
 * cached reads only. Heavy logic belongs in Supabase or the AI service.
 */
import { GoQuery, LISTING_ID_PATTERN } from '@comemorocco/shared';
import { Hono } from 'hono';
import { cors } from 'hono/cors';

import { resolveFromSupabase, resolveLocal, type ResolvedLink, withSubId } from './affiliates';
import { fetchWordPress } from './content';

export interface Env {
  SITE_URL: string;
  WORDPRESS_URL: string;
  ALLOWED_ORIGINS?: string;
  SUPABASE_URL?: string;
  SUPABASE_SERVICE_ROLE_KEY?: string;
}

type Ctx = { Bindings: Env };

export function createApp(deps: { fetch?: typeof fetch; now?: () => Date; uuid?: () => string } = {}) {
  const doFetch = deps.fetch ?? ((input: RequestInfo | URL, init?: RequestInit) => fetch(input, init));
  const now = deps.now ?? (() => new Date());
  const uuid = deps.uuid ?? (() => crypto.randomUUID());
  const app = new Hono<Ctx>();

  app.use('/v1/*', async (c, next) => {
    const allowed = (c.env.ALLOWED_ORIGINS ?? '').split(',').map((s) => s.trim()).filter(Boolean);
    return cors({ origin: allowed, allowMethods: ['GET'], maxAge: 3600 })(c, next);
  });

  app.get('/health', (c) =>
    c.json({ status: 'ok', supabase: Boolean(c.env.SUPABASE_URL && c.env.SUPABASE_SERVICE_ROLE_KEY) }),
  );

  app.get('/go/:listingId', async (c) => {
    const listingId = c.req.param('listingId');
    const site = c.env.SITE_URL;
    if (!LISTING_ID_PATTERN.test(listingId)) return c.redirect(site, 302);

    const query = GoQuery.safeParse(c.req.query());
    const params = query.success ? query.data : GoQuery.parse({});

    let link: ResolvedLink | null = null;
    try {
      link =
        c.env.SUPABASE_URL && c.env.SUPABASE_SERVICE_ROLE_KEY
          ? await resolveFromSupabase(listingId, c.env.SUPABASE_URL, c.env.SUPABASE_SERVICE_ROLE_KEY, doFetch)
          : resolveLocal(listingId);
    } catch (err) {
      console.error(JSON.stringify({ event: 'affiliate_lookup_failed', listingId, error: String(err) }));
      link = resolveLocal(listingId);
    }

    if (!link) {
      console.warn(JSON.stringify({ event: 'affiliate_unknown_listing', listingId }));
      return c.redirect(site, 302);
    }

    const clickId = uuid();
    const click = {
      id: clickId,
      listing_id: link.listingId,
      program_id: link.programId,
      partner: link.partner,
      source: params.src,
      campaign: params.cmp ?? null,
      trip_id: params.trip ?? null,
      anonymous_id: params.aid ?? null,
      platform: params.platform ?? null,
      country: (c.req.raw as Request & { cf?: { country?: string } }).cf?.country ?? null,
      referrer_host: safeHost(c.req.header('referer')),
      created_at: now().toISOString(),
    };
    const record = recordClick(c.env, click, doFetch);
    // Never make the traveller wait for logging.
    try {
      c.executionCtx.waitUntil(record);
    } catch {
      await record; // no execution context (tests, local scripts)
    }

    c.header('Cache-Control', 'no-store');
    c.header('Referrer-Policy', 'no-referrer');
    return c.redirect(withSubId(link.url, clickId), 302);
  });

  app.get('/v1/content', async (c) => {
    const limit = Math.min(Math.max(Number(c.req.query('limit') ?? 8) || 8, 1), 20);
    const destination = (c.req.query('destination') ?? '').replace(/[^a-z-]/gi, '').slice(0, 40) || null;
    const cacheKey = new Request(`https://cache.internal/v1/content?d=${destination ?? ''}&l=${limit}`);
    const cache = typeof caches !== 'undefined' ? (caches as unknown as { default: Cache }).default : null;

    const cached = await cache?.match(cacheKey);
    if (cached) {
      const body = (await cached.json()) as { items: unknown[] };
      return c.json({ ...body, source: 'cache' });
    }
    try {
      const items = await fetchWordPress(c.env.WORDPRESS_URL, c.env.SITE_URL, { destination, limit }, doFetch);
      const body = { items, source: 'live' as const };
      await cache?.put(
        cacheKey,
        new Response(JSON.stringify(body), { headers: { 'Cache-Control': 'public, max-age=600' } }),
      );
      return c.json(body, 200, { 'Cache-Control': 'public, max-age=300' });
    } catch (err) {
      console.error(JSON.stringify({ event: 'wordpress_fetch_failed', error: String(err) }));
      // The app falls back to its bundled catalog on an empty list.
      return c.json({ items: [], source: 'fallback' as const }, 200, { 'Cache-Control': 'no-store' });
    }
  });

  app.notFound((c) => c.json({ error: 'not_found' }, 404));
  app.onError((err, c) => {
    console.error(JSON.stringify({ event: 'unhandled', error: String(err) }));
    return c.json({ error: 'internal_error' }, 500);
  });

  return app;
}

function safeHost(value: string | undefined): string | null {
  if (!value) return null;
  try {
    return new URL(value).hostname;
  } catch {
    return null;
  }
}

async function recordClick(env: Env, click: Record<string, unknown>, doFetch: typeof fetch): Promise<void> {
  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE_KEY) {
    console.log(JSON.stringify({ event: 'affiliate_click', ...click }));
    return;
  }
  try {
    const response = await doFetch(new URL('/rest/v1/affiliate_clicks', env.SUPABASE_URL).toString(), {
      method: 'POST',
      headers: {
        apikey: env.SUPABASE_SERVICE_ROLE_KEY,
        Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
        'Content-Type': 'application/json',
        Prefer: 'return=minimal',
      },
      body: JSON.stringify(click),
    });
    if (!response.ok) throw new Error(`insert failed: ${response.status}`);
  } catch (err) {
    // Losing a click log must never break the redirect.
    console.error(JSON.stringify({ event: 'affiliate_click_log_failed', id: click.id, error: String(err) }));
  }
}

export default createApp();
