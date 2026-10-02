/**
 * Links words in AI answers to comemorocco.com: activities ("hiking", "camel
 * ride", "hammam"…) to their activity pages and city names to their guides.
 * Each page is linked once per answer (its first mention), at most
 * MAX_LINKS per answer, whole words only.
 */

export interface LinkTerm {
  /** Lower-case phrases that should link, in any supported language. */
  phrases: string[];
  url: string;
}

export type Segment = { text: string; url?: string };

export const MAX_LINKS = 6;

const SITE = 'https://comemorocco.com';

/** Activity pages on the site and the words travellers use for them. */
export const ACTIVITY_TERMS: LinkTerm[] = [
  { url: `${SITE}/activity/hiking-morocco-atlas-mountains/`, phrases: ['hiking', 'hike', 'hikes', 'trekking', 'trek', 'treks', 'randonnée', 'randonnées', 'senderismo', 'المشي لمسافات طويلة'] },
  { url: `${SITE}/activity/camel-riding-sahara-desert-morocco/`, phrases: ['camel ride', 'camel rides', 'camel riding', 'camel trek', 'balade à dos de chameau', 'paseo en camello', 'ركوب الجمال'] },
  { url: `${SITE}/activity/desert-camping-sahara-morocco-luxury/`, phrases: ['desert camp', 'desert camps', 'desert camping', 'glamping', 'bivouac', 'campamento en el desierto', 'camp dans le désert', 'مخيم'] },
  { url: `${SITE}/activity/morocco-imperial-city-tours-marrakech-fez/`, phrases: ['imperial cities', 'imperial city', 'villes impériales', 'ciudades imperiales', 'المدن الإمبراطورية'] },
  { url: `${SITE}/activity/morocco-shopping-tours-souks-medina/`, phrases: ['souks', 'souk', 'zocos', 'zoco', 'الأسواق'] },
  { url: `${SITE}/activity/moroccan-cooking-classes-marrakech-riad/`, phrases: ['cooking class', 'cooking classes', 'cours de cuisine', 'clase de cocina', 'clases de cocina', 'دروس الطبخ'] },
  { url: `${SITE}/activity/quad-biking-morocco-desert-adventure/`, phrases: ['quad biking', 'quad bike', 'quad', 'atv', 'buggy'] },
  { url: `${SITE}/activity/morocco-historical-tours-unesco-kasbahs/`, phrases: ['kasbahs', 'kasbah', 'unesco'] },
  { url: `${SITE}/activity/traditional-moroccan-hammam-steam-bath/`, phrases: ['hammam', 'hammams', 'حمام'] },
  { url: `${SITE}/activity/hot-air-ballooning-morocco-atlas-sunrise/`, phrases: ['hot air balloon', 'hot-air balloon', 'hot air ballooning', 'balloon ride', 'montgolfière', 'globo aerostático', 'منطاد'] },
];

const fold = (s: string) =>
  s
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * Splits text into plain and linked segments. `used` carries the URLs already
 * linked earlier in the same answer and is updated in place.
 */
export function linkSegments(text: string, terms: LinkTerm[], used: Set<string>): Segment[] {
  if (used.size >= MAX_LINKS || !text) return [{ text }];
  const folded = fold(text);
  // Positions found in the folded text are used to cut the original, which
  // is only safe when folding kept the length (no accented letters). Otherwise
  // match on the plain lower-cased text, with phrases listed accents included.
  const sameLength = folded.length === text.length;
  const source = sameLength ? folded : text.toLowerCase();
  let best: { start: number; end: number; url: string } | null = null;
  for (const term of terms) {
    if (used.has(term.url)) continue;
    for (const phrase of term.phrases) {
      const needle = sameLength ? fold(phrase) : phrase.toLowerCase();
      const match = new RegExp(`(^|[^\\p{L}\\p{N}])(${escape(needle)})(?![\\p{L}\\p{N}])`, 'u').exec(source);
      if (!match) continue;
      const start = match.index + match[1]!.length;
      // Earliest mention wins; at the same place the longer phrase wins.
      if (!best || start < best.start || (start === best.start && start + needle.length > best.end)) {
        best = { start, end: start + needle.length, url: term.url };
      }
    }
  }
  if (!best) return [{ text }];
  used.add(best.url);
  const before = text.slice(0, best.start);
  const linked = { text: text.slice(best.start, best.end), url: best.url };
  const rest = linkSegments(text.slice(best.end), terms, used);
  return [...(before ? [{ text: before }] : []), linked, ...rest];
}
