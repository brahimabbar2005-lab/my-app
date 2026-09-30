#!/usr/bin/env node
/**
 * Checks a live Supabase project against what the app expects, using only
 * the publishable key (never the secret key).
 *
 *   SUPABASE_URL=https://<ref>.supabase.co SUPABASE_PUBLISHABLE_KEY=sb_publishable_... \
 *     node scripts/check-supabase-live.mjs
 *
 * Anonymous: public tables are readable, private tables show nothing, writes
 * that need an account are refused.
 * With SUPABASE_TEST_ACCESS_TOKEN (a signed-in user's access token) it also
 * round-trips a throwaway trip through sync_trip and deletes it again.
 */
import { randomUUID } from 'node:crypto';

const base = (process.env.SUPABASE_URL ?? process.env.EXPO_PUBLIC_SUPABASE_URL ?? '').replace(/\/$/, '');
const key = process.env.SUPABASE_PUBLISHABLE_KEY ?? process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? '';
const token = process.env.SUPABASE_TEST_ACCESS_TOKEN;
if (!base || !key) {
  console.error('Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY.');
  process.exit(2);
}
if (key.startsWith('sb_secret_') || key.includes('service_role')) {
  console.error('Refusing to run with a secret key: use the publishable key.');
  process.exit(2);
}

let failures = 0;
const check = (ok, label, detail = '') => {
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${label}${detail ? ` — ${detail}` : ''}`);
  if (!ok) failures += 1;
};

async function call(path, { method = 'GET', body, bearer, headers = {} } = {}) {
  const res = await fetch(`${base}${path}`, {
    method,
    headers: {
      apikey: key,
      ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}),
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    /* not JSON */
  }
  return { status: res.status, json, text };
}

// Public catalogue.
for (const table of ['destinations', 'listings']) {
  const r = await call(`/rest/v1/${table}?select=id&limit=100`);
  check(r.status === 200 && Array.isArray(r.json) && r.json.length > 0, `anon reads ${table}`, `${r.json?.length ?? r.status} rows`);
}

// Private data is invisible to anonymous callers.
for (const table of ['trips', 'trip_items', 'saved_places', 'profiles', 'bookings', 'ai_sessions', 'ai_messages', 'affiliate_clicks', 'audit_log']) {
  const r = await call(`/rest/v1/${table}?select=*&limit=1`);
  const hidden = (r.status === 200 && Array.isArray(r.json) && r.json.length === 0) || r.status === 401 || r.status === 403;
  check(hidden, `anon sees no ${table}`, `HTTP ${r.status}`);
}
{
  const r = await call('/rest/v1/analytics_events?select=*&limit=1');
  check(r.status >= 400, 'anon cannot read analytics_events', `HTTP ${r.status}`);
}
{
  const r = await call('/rest/v1/rpc/sync_trip', { method: 'POST', body: { trip: {}, days: [], items: [] } });
  check(r.status >= 400, 'anon cannot call sync_trip', `HTTP ${r.status}`);
}
{
  const r = await call('/auth/v1/settings');
  check(r.status === 200 && r.json?.external?.email === true, 'email sign-in is enabled');
}

if (token) {
  const user = await call('/auth/v1/user', { bearer: token });
  check(user.status === 200 && !!user.json?.id, 'access token is valid', user.json?.email ?? `HTTP ${user.status}`);
  const uid = user.json?.id;
  const tripId = randomUUID();
  const dayId = randomUUID();
  const sync = await call('/rest/v1/rpc/sync_trip', {
    method: 'POST',
    bearer: token,
    body: {
      trip: { id: tripId, user_id: uid, title: 'Live check (deleted automatically)', travelers_adults: 2 },
      days: [{ id: dayId, day_number: 1 }],
      items: [{ id: randomUUID(), trip_day_id: dayId, item_type: 'destination', ref_id: 'marrakech', title: 'Marrakech', position: 0 }],
    },
  });
  check(sync.status < 300, 'signed-in sync_trip succeeds', sync.status < 300 ? '' : sync.text.slice(0, 200));
  const back = await call(`/rest/v1/trips?id=eq.${tripId}&select=id,trip_items(ref_id)`, { bearer: token });
  check(back.json?.[0]?.trip_items?.[0]?.ref_id === 'marrakech', 'trip reads back with its items');
  const anon = await call(`/rest/v1/trips?id=eq.${tripId}&select=id`);
  check(Array.isArray(anon.json) && anon.json.length === 0, 'the trip stays invisible to anon');
  const del = await call(`/rest/v1/trips?id=eq.${tripId}`, { method: 'DELETE', bearer: token });
  check(del.status < 300, 'test trip deleted', `HTTP ${del.status}`);
} else {
  console.log('skip signed-in round trip (set SUPABASE_TEST_ACCESS_TOKEN to run it)');
}

console.log(failures ? `\n${failures} check(s) failed` : '\nall live checks passed');
process.exit(failures ? 1 : 0);
