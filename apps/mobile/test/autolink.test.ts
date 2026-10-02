import { describe, expect, it } from 'vitest';

import { ACTIVITY_TERMS, linkSegments, MAX_LINKS } from '../src/lib/autolink';

const terms = [
  ...ACTIVITY_TERMS,
  { url: 'https://comemorocco.com/destinations/marrakech/', phrases: ['marrakech', 'marrakesh', 'مراكش'] },
  { url: 'https://comemorocco.com/destinations/fes/', phrases: ['fes', 'fès', 'fez'] },
];

const links = (text: string, used = new Set<string>()) =>
  linkSegments(text, terms, used)
    .filter((s) => s.url)
    .map((s) => [s.text, s.url!.replace('https://comemorocco.com', '')]);

describe('linkSegments', () => {
  it('links activities and cities once, keeping the original wording', () => {
    expect(links('Hiking in the Atlas, then more hiking near Marrakech and a Camel ride.')).toEqual([
      ['Hiking', '/activity/hiking-morocco-atlas-mountains/'],
      ['Marrakech', '/destinations/marrakech/'],
      ['Camel ride', '/activity/camel-riding-sahara-desert-morocco/'],
    ]);
  });

  it('matches whole words and the longest phrase', () => {
    expect(links('Festivals and fesenjan are not Fes.')).toEqual([['Fes', '/destinations/fes/']]);
    expect(links('Book a hot air balloon at sunrise.')).toEqual([['hot air balloon', '/activity/hot-air-ballooning-morocco-atlas-sunrise/']]);
  });

  it('works in French and Arabic and keeps the text intact', () => {
    const text = 'Une randonnée à Fès, puis le hammam.';
    const segments = linkSegments(text, terms, new Set());
    expect(segments.map((s) => s.text).join('')).toBe(text);
    expect(links(text)).toEqual([
      ['randonnée', '/activity/hiking-morocco-atlas-mountains/'],
      ['Fès', '/destinations/fes/'],
      ['hammam', '/activity/traditional-moroccan-hammam-steam-bath/'],
    ]);
    expect(links('زيارة مراكش ثم حمام')).toEqual([
      ['مراكش', '/destinations/marrakech/'],
      ['حمام', '/activity/traditional-moroccan-hammam-steam-bath/'],
    ]);
  });

  it('shares the budget across an answer', () => {
    const used = new Set<string>();
    links('hiking, souks, hammam, quad, kasbah, cooking class', used);
    expect(used.size).toBe(MAX_LINKS);
    expect(links('Marrakech and Fes', used)).toEqual([]);
  });
});
