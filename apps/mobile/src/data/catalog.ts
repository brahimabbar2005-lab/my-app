/**
 * Catalog data (generated from the AI knowledge base by
 * scripts/generate_catalog.py). Used as the offline/fallback source; when
 * Supabase is configured the same shapes come from the database.
 */
import type { Locale } from '@comemorocco/i18n';

import raw from './catalog.generated.json';

export type ListingCategory = 'stay' | 'experience' | 'car' | 'transfer' | 'driver';

export interface Destination {
  id: string;
  name: Record<Locale, string>;
  region: string;
  lat: number;
  lng: number;
  hue: string;
  tagline: string;
  guide_url: string | null;
  listing_count: number;
  article_count: number;
}

export interface Listing {
  id: string;
  kind: 'program' | 'activity';
  category: ListingCategory;
  title: string;
  subtitle: string;
  destination: string | null;
  partner: string;
}

export interface Article {
  id: string;
  wordpress_post_id: number | null;
  title: string;
  excerpt: string;
  canonical_url: string;
  destination: string | null;
  topic: string | null;
}

interface Catalog {
  destinations: Destination[];
  listings: Listing[];
  articles: Article[];
}

export const catalog = raw as unknown as Catalog;

export function destinationName(d: Destination, locale: Locale): string {
  return d.name[locale] ?? d.name.en;
}

export function getDestination(id: string): Destination | undefined {
  return catalog.destinations.find((d) => d.id === id);
}

/** Listings for a category/city. City-specific experiences come before country-wide partners. */
export function listingsFor({ category, destination }: { category?: ListingCategory; destination?: string | null }) {
  return catalog.listings
    .filter((l) => (!category || l.category === category) && (!destination || l.destination === destination))
    .sort((a, b) => Number(a.destination === null) - Number(b.destination === null));
}

export function articlesFor(destination?: string | null, limit = 10): Article[] {
  const pool = destination ? catalog.articles.filter((a) => a.destination === destination) : catalog.articles;
  return pool.slice(0, limit);
}

/** Simple local search across destinations, listings and articles. */
export function searchCatalog(query: string, locale: Locale) {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return { destinations: [], listings: [], articles: [] };
  const has = (s: string | null | undefined) => !!s && s.toLowerCase().includes(q);
  return {
    destinations: catalog.destinations.filter((d) => has(destinationName(d, locale)) || has(d.name.en) || has(d.tagline)),
    listings: catalog.listings.filter((l) => has(l.title) || has(l.subtitle)).slice(0, 20),
    articles: catalog.articles.filter((a) => has(a.title)).slice(0, 10),
  };
}
