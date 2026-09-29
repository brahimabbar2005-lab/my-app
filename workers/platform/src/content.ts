/**
 * One-way WordPress ingestion (Master Plan §23–24, §35). Reads the public
 * WordPress REST API and returns light references (title, excerpt, image,
 * canonical URL). WordPress stays the editorial source; nothing is written
 * back to it from here.
 */
import type { ContentItem } from '@comemorocco/shared';

interface WpPost {
  id: number;
  link: string;
  modified_gmt?: string;
  title?: { rendered?: string };
  excerpt?: { rendered?: string };
  jetpack_featured_media_url?: string;
  _embedded?: { 'wp:featuredmedia'?: { source_url?: string }[] };
}

const ENTITIES: Record<string, string> = {
  '&amp;': '&',
  '&quot;': '"',
  '&#039;': "'",
  '&#8217;': '’',
  '&#8216;': '‘',
  '&#8220;': '“',
  '&#8221;': '”',
  '&#8211;': '–',
  '&#8212;': '—',
  '&hellip;': '…',
  '&#8230;': '…',
  '&nbsp;': ' ',
  '&lt;': '<',
  '&gt;': '>',
};

export function plainText(html: string | undefined, max = 220): string {
  const text = (html ?? '')
    .replace(/<[^>]*>/g, ' ')
    .replace(/&[#a-z0-9]+;/gi, (e) => ENTITIES[e.toLowerCase()] ?? ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text;
}

export function toContentItem(post: WpPost, siteUrl: string, destination: string | null): ContentItem | null {
  if (!post?.id || !post.link) return null;
  // Only canonical site URLs are ever returned to the app.
  if (!post.link.startsWith(siteUrl)) return null;
  const image = post._embedded?.['wp:featuredmedia']?.[0]?.source_url ?? post.jetpack_featured_media_url ?? null;
  return {
    id: `wp-${post.id}`,
    source: 'wordpress',
    wordpress_post_id: post.id,
    canonical_url: post.link,
    title: plainText(post.title?.rendered, 200),
    excerpt: plainText(post.excerpt?.rendered),
    image_url: image && /^https:\/\//.test(image) ? image : null,
    categories: [],
    destination,
    updated_at: post.modified_gmt ? `${post.modified_gmt}Z` : new Date(0).toISOString(),
  };
}

export async function fetchWordPress(
  wordpressUrl: string,
  siteUrl: string,
  { destination, limit }: { destination: string | null; limit: number },
  fetcher: typeof fetch = fetch,
): Promise<ContentItem[]> {
  const url = new URL('/wp-json/wp/v2/posts', wordpressUrl);
  url.searchParams.set('per_page', String(limit));
  url.searchParams.set('_embed', 'wp:featuredmedia');
  url.searchParams.set('_fields', 'id,link,modified_gmt,title,excerpt,jetpack_featured_media_url,_embedded,_links');
  if (destination) url.searchParams.set('search', destination);
  const response = await fetcher(url.toString(), { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`WordPress responded ${response.status}`);
  const posts = (await response.json()) as WpPost[];
  return posts.map((p) => toContentItem(p, siteUrl, destination)).filter((x): x is ContentItem => x !== null);
}
