/**
 * Affiliate integration layer (Master Plan §7, §22–23).
 *
 * Resolution: listing id → active partner URL, from Supabase
 * (affiliate_links) when configured, else from the generated map built from
 * the editorial affiliate spreadsheet. Partner URLs never leave the server
 * except as the redirect target.
 *
 * Sub-ids: each partner network names its tracking parameter differently, so
 * adapters are per network. The parameter names below must be confirmed in
 * each partner dashboard before relying on them for reconciliation; an
 * unknown parameter is ignored by the partner, so a wrong guess costs
 * attribution, not the click.
 */
import generated from './affiliate-links.generated.json';

export interface ResolvedLink {
  listingId: string;
  url: string;
  partner: string;
  programId: string | null;
}

interface Adapter {
  /** Query parameter the network reads a sub-id / click reference from. */
  subIdParam: string | null;
}

const ADAPTERS: Record<string, Adapter> = {
  // Travelpayouts short links (*.tpx.li) — verify in the Travelpayouts dashboard.
  travelpayouts: { subIdParam: 'sub_id' },
  // GetYourGuide partner links carry a campaign parameter — verify in the GYG partner portal.
  getyourguide: { subIdParam: 'cmp' },
};

export function networkFor(url: string): string {
  const host = new URL(url).hostname;
  if (host.endsWith('tpx.li') || host.endsWith('tp.media')) return 'travelpayouts';
  if (host === 'gyg.me' || host.endsWith('getyourguide.com')) return 'getyourguide';
  return 'unknown';
}

/** Adds the click id as the network's sub-id. Never changes scheme/host/path. */
export function withSubId(url: string, clickId: string): string {
  const adapter = ADAPTERS[networkFor(url)];
  if (!adapter?.subIdParam) return url;
  const target = new URL(url);
  target.searchParams.set(adapter.subIdParam, clickId);
  return target.toString();
}

const LOCAL = (generated as { links: Record<string, { url: string; partner: string; program_id: string | null }> }).links;

export function resolveLocal(listingId: string): ResolvedLink | null {
  const link = LOCAL[listingId];
  if (!link || !/^https:\/\//.test(link.url)) return null;
  return { listingId, url: link.url, partner: link.partner, programId: link.program_id };
}

export async function resolveFromSupabase(
  listingId: string,
  supabaseUrl: string,
  serviceKey: string,
  fetcher: typeof fetch = fetch,
): Promise<ResolvedLink | null> {
  const endpoint = new URL('/rest/v1/affiliate_links', supabaseUrl);
  endpoint.searchParams.set('listing_id', `eq.${listingId}`);
  endpoint.searchParams.set('active', 'eq.true');
  endpoint.searchParams.set('select', 'url,partner,program_id');
  endpoint.searchParams.set('limit', '1');
  const response = await fetcher(endpoint.toString(), {
    headers: { apikey: serviceKey, Authorization: `Bearer ${serviceKey}` },
  });
  if (!response.ok) throw new Error(`affiliate_links lookup failed: ${response.status}`);
  const rows = (await response.json()) as { url: string; partner: string; program_id: string | null }[];
  const row = rows[0];
  if (!row || !/^https:\/\//.test(row.url)) return null;
  return { listingId, url: row.url, partner: row.partner, programId: row.program_id };
}
