/**
 * Editorial content references (Master Plan §23–24, §35–36).
 *
 * WordPress stays the editorial source. The platform keeps a light cached
 * reference (title, excerpt, image, destination) and always links back to the
 * canonical comemorocco.com URL with app attribution.
 */
import { z } from 'zod';

export const ContentItem = z.object({
  id: z.string(),
  source: z.literal('wordpress'),
  wordpress_post_id: z.number().int(),
  canonical_url: z.url(),
  title: z.string(),
  excerpt: z.string().default(''),
  image_url: z.url().nullish(),
  categories: z.array(z.string()).default([]),
  destination: z.string().nullish(),
  updated_at: z.string(),
});
export type ContentItem = z.infer<typeof ContentItem>;

export const ContentList = z.object({
  items: z.array(ContentItem),
  source: z.enum(['live', 'cache', 'fallback']),
});
export type ContentList = z.infer<typeof ContentList>;

export const SITE_URL = 'https://comemorocco.com';

/**
 * Canonical website URL with app attribution. Existing utm_* values win, so a
 * link that already carries a campaign keeps it.
 */
export function withAppUtm(url: string, campaign = 'content', medium = 'mobile'): string {
  const parsed = new URL(url);
  if (!parsed.searchParams.has('utm_source')) parsed.searchParams.set('utm_source', 'app');
  if (!parsed.searchParams.has('utm_medium')) parsed.searchParams.set('utm_medium', medium);
  if (!parsed.searchParams.has('utm_campaign')) parsed.searchParams.set('utm_campaign', campaign);
  return parsed.toString();
}

/** Only comemorocco.com links get app attribution; partner links are left alone. */
export function isSiteUrl(url: string): boolean {
  try {
    const host = new URL(url).hostname;
    return host === 'comemorocco.com' || host.endsWith('.comemorocco.com');
  } catch {
    return false;
  }
}
