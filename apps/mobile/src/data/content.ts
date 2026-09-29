/**
 * ComeMorocco articles. Live from the platform worker (/v1/content, which
 * reads the WordPress REST API with caching); falls back to the bundled
 * catalog so the app is useful offline and before the worker is deployed.
 */
import { ContentList } from '@comemorocco/shared';
import { useEffect, useState } from 'react';

import { config } from '@/lib/config';

import { type Article, articlesFor } from './catalog';

export type ArticleSource = 'live' | 'cache' | 'fallback';

export function useArticles(destination?: string | null, limit = 8) {
  const [state, setState] = useState<{ items: Article[]; source: ArticleSource }>(() => ({
    items: articlesFor(destination, limit),
    source: 'fallback',
  }));

  useEffect(() => {
    let alive = true;
    const controller = new AbortController();
    const url = new URL('/v1/content', config.platformUrl);
    url.searchParams.set('limit', String(limit));
    if (destination) url.searchParams.set('destination', destination);
    fetch(url.toString(), { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((json) => {
        const parsed = ContentList.safeParse(json);
        if (!alive || !parsed.success || !parsed.data.items.length) return;
        setState({
          source: parsed.data.source,
          items: parsed.data.items.map((i) => ({
            id: i.id,
            wordpress_post_id: i.wordpress_post_id,
            title: i.title,
            excerpt: i.excerpt,
            canonical_url: i.canonical_url,
            destination: i.destination ?? null,
            topic: null,
          })),
        });
      })
      .catch(() => {
        // Keep the bundled fallback.
      });
    return () => {
      alive = false;
      controller.abort();
    };
  }, [destination, limit]);

  return state;
}
