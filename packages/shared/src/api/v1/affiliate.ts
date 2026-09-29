/**
 * Affiliate redirect contract (Master Plan §22–24).
 *
 *   GET {worker}/go/:listingId?src=ai&cmp=...&trip=...&aid=...
 *
 * The app only ever knows the listing id. The partner URL, affiliate id and
 * sub-id format are resolved by the worker and never shipped to clients.
 *
 * Affiliate lifecycle states are distinct and never collapsed:
 *   click → conversion → booking (confirmed by network) → commission (approved)
 */
import { z } from 'zod';

import { Source } from './events';

export const LISTING_ID_PATTERN = /^[a-z0-9][a-z0-9_-]{0,127}$/i;

export const GoQuery = z.object({
  src: Source.default('unknown'),
  cmp: z.string().max(100).optional(),
  trip: z.string().max(64).optional(),
  aid: z.string().min(8).max(64).optional(),
  platform: z.enum(['ios', 'android', 'web']).optional(),
});
export type GoQuery = z.infer<typeof GoQuery>;

export const AffiliateLifecycle = z.enum(['click', 'conversion', 'booking', 'commission']);
export type AffiliateLifecycle = z.infer<typeof AffiliateLifecycle>;

/** How a partner reports conversions. Never assume an API exists. */
export const ConversionCapability = z.enum(['api', 'webhook', 'report_import', 'manual']);
export type ConversionCapability = z.infer<typeof ConversionCapability>;

export function goUrl(
  workerBaseUrl: string,
  listingId: string,
  query: Partial<GoQuery> = {},
): string {
  if (!LISTING_ID_PATTERN.test(listingId)) throw new Error(`invalid listing id: ${listingId}`);
  const url = new URL(`/go/${encodeURIComponent(listingId)}`, workerBaseUrl);
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') url.searchParams.set(key, String(value));
  }
  return url.toString();
}
