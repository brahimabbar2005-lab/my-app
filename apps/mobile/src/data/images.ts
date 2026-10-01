/**
 * Photos for cards: each comemorocco.com page's own share image (og:image),
 * collected by scripts/fetch_page_images.py. Pages without one keep the
 * patterned tile.
 */
import raw from './images.generated.json';

const images = raw as Record<string, string>;

export function pageImage(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  const withSlash = url.endsWith('/') ? url : `${url}/`;
  return images[url] ?? images[withSlash];
}
