import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { LOCALES } from '@comemorocco/i18n';
import { LISTING_ID_PATTERN } from '@comemorocco/shared';
import { describe, expect, it } from 'vitest';

import workerLinks from '../../../workers/platform/src/affiliate-links.generated.json';
import { articlesForInterests, catalog, listingsFor, searchCatalog } from '../src/data/catalog';
import { EMERGENCY_CONTACTS } from '../src/data/essentials';

const links = (workerLinks as { links: Record<string, { url: string }> }).links;

describe('catalog integrity', () => {
  it('ships no partner URLs inside the app bundle', () => {
    const raw = readFileSync(join(__dirname, '../src/data/catalog.generated.json'), 'utf8');
    expect(raw).not.toMatch(/gyg\.me|tpx\.li|getyourguide\.com|booking\.com/);
  });

  it('every listing can be resolved by the /go worker', () => {
    for (const listing of catalog.listings) {
      expect(LISTING_ID_PATTERN.test(listing.id)).toBe(true);
      expect(links[listing.id], listing.id).toBeDefined();
    }
  });

  it('every article links to the canonical site', () => {
    for (const article of catalog.articles) expect(article.canonical_url).toMatch(/^https:\/\/comemorocco\.com\//);
  });

  it('every destination is named in every UI language and links to a real hub or guide', () => {
    for (const d of catalog.destinations) {
      for (const locale of LOCALES) {
        expect(d.name[locale], `${d.id}.${locale}`).toBeTruthy();
        expect(d.tagline[locale], `${d.id} tagline ${locale}`).toBeTruthy();
      }
      if (d.guide_url) expect(d.guide_url).toMatch(/^https:\/\/comemorocco\.com\//);
    }
    expect(catalog.destinations.find((d) => d.id === 'fes')?.guide_url).toBe('https://comemorocco.com/destinations/fes/');
  });

  it('lists city experiences before country-wide partners', () => {
    const items = listingsFor({ category: 'experience' });
    const firstCountryWide = items.findIndex((l) => l.destination === null);
    expect(items.slice(firstCountryWide).every((l) => l.destination === null)).toBe(true);
  });

  it('searches across destinations, listings and guides', () => {
    const results = searchCatalog('merzouga', 'en');
    expect(results.destinations.map((d) => d.id)).toContain('merzouga');
    expect(results.listings.length).toBeGreaterThan(0);
    expect(searchCatalog('m', 'en').listings).toEqual([]);
  });
});

describe('essentials', () => {
  it('emergency numbers in the app match the database seed and carry a source', () => {
    const seed = readFileSync(join(__dirname, '../../../supabase/seed/emergency_contacts.sql'), 'utf8');
    for (const c of EMERGENCY_CONTACTS) {
      expect(c.source).toBeTruthy();
      expect(seed).toContain(`('${c.id}', 'MA', '${c.service}', '${c.label}', '${c.number}'`);
    }
  });
});

describe('interests', () => {
  it('puts guides matching the traveller\'s interests first', () => {
    const desert = articlesForInterests(['desert'], 5);
    expect(desert).toHaveLength(5);
    expect(desert.every((a) => /desert|sahara|merzouga|dunes|camel/i.test(a.title))).toBe(true);
    expect(articlesForInterests([], 3)).toEqual(catalog.articles.slice(0, 3));
  });
});
