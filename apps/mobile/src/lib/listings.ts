/**
 * The live catalogue: offers bundled with the app plus the ones admins add in
 * Supabase (hotels, riads, hostels, tours…). Published offers only; RLS
 * hides drafts. Without Supabase, or offline, the bundled offers remain.
 */
import { useEffect, useState } from 'react';

import { catalog, type Listing, type ListingCategory, type ListingSubtype } from '@/data/catalog';

import { supabase } from './supabase';

interface Row {
  id: string;
  kind: Listing['kind'];
  category: ListingCategory;
  subtype: ListingSubtype | null;
  title: string;
  subtitle: string | null;
  description: string | null;
  destination_id: string | null;
  partner_name: string | null;
  price_from_minor: number | null;
  currency: string | null;
  image_url: string | null;
  website_url: string | null;
}

export function fromRow(row: Row): Listing {
  return {
    id: row.id,
    kind: row.kind,
    category: row.category,
    subtype: row.subtype,
    title: row.title,
    subtitle: row.subtitle ?? '',
    description: row.description,
    destination: row.destination_id,
    partner: row.partner_name ?? '',
    priceFromMinor: row.price_from_minor,
    currency: row.currency,
    imageUrl: row.image_url,
    websiteUrl: row.website_url,
  };
}

/** Bundled offers, overridden by and extended with the live rows. */
export function mergeListings(bundled: Listing[], live: Listing[]): Listing[] {
  const byId = new Map(bundled.map((l) => [l.id, l]));
  for (const l of live) byId.set(l.id, { ...byId.get(l.id), ...l });
  return [...byId.values()];
}

const COLUMNS =
  'id,kind,category,subtype,title,subtitle,description,destination_id,partner_name,price_from_minor,currency,image_url,website_url';

let cache: Listing[] | null = null;
let pending: Promise<Listing[]> | null = null;
const listeners = new Set<(l: Listing[]) => void>();

async function load(): Promise<Listing[]> {
  if (!supabase) return catalog.listings;
  const { data, error } = await supabase.from('listings').select(COLUMNS).eq('status', 'published').limit(1000);
  if (error || !data) return cache ?? catalog.listings;
  return mergeListings(catalog.listings, (data as Row[]).map(fromRow));
}

/** Reloads the live catalogue (after an admin saves an offer). */
export async function refreshListings(): Promise<void> {
  pending = load();
  cache = await pending;
  pending = null;
  listeners.forEach((fn) => fn(cache!));
}

export function useListings(): Listing[] {
  const [listings, setListings] = useState<Listing[]>(cache ?? catalog.listings);
  useEffect(() => {
    listeners.add(setListings);
    if (!cache && !pending) refreshListings();
    return () => {
      listeners.delete(setListings);
    };
  }, []);
  return listings;
}
