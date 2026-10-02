/**
 * Turns a day-by-day plan in an AI answer ("Days 1–2: Marrakech — …") into
 * trip days, so the traveller can save it with one tap. Pure and
 * deterministic: nothing is saved until they tap, and only what is written
 * in the answer is used.
 */

export interface PlanDay {
  day: number;
  text: string;
  /** Catalogue destinations named on that day, in order of appearance. */
  destinations: string[];
}

export interface NamedPlace {
  id: string;
  names: string[];
}

const MAX_DAY = 30;
const DIGITS: Record<string, string> = { '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9' };
const DAY_LINE =
  /^\s*(?:[-*•]\s*)?(?:\*\*)?\s*(?:days?|jours?|d[ií]as?|اليوم|الأيام|يوم)\s*([0-9٠-٩]{1,2})(?:\s*(?:-|–|—|à|a|to|al|إلى)\s*([0-9٠-٩]{1,2}))?\s*(?:\*\*)?\s*[:：.\-–—]\s*(?:\*\*)?\s*(.+)$/i;

const fold = (s: string) =>
  s
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();

/** Position of a whole-word match ("Fes" must not match "festival"); -1 if none. */
function wordIndex(haystack: string, name: string): number {
  const needle = fold(name).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = new RegExp(`(^|[^a-z0-9])${needle}(?![a-z0-9])`).exec(haystack);
  return match ? match.index + match[1]!.length : -1;
}

const toNumber = (s: string) => Number(s.replace(/[٠-٩]/g, (d) => DIGITS[d]!));

export function parseItinerary(text: string, places: NamedPlace[]): PlanDay[] {
  const days = new Map<number, PlanDay>();
  for (const rawLine of text.split('\n')) {
    const match = DAY_LINE.exec(rawLine);
    if (!match) continue;
    const from = toNumber(match[1]!);
    const to = match[2] ? toNumber(match[2]) : from;
    const body = match[3]!.replace(/\*\*/g, '').trim();
    if (!body || from < 1 || to < from || to > MAX_DAY) continue;
    const folded = fold(body);
    const found = places
      .map((p) => ({ id: p.id, at: Math.min(...p.names.map((n) => wordIndex(folded, n)).filter((i) => i >= 0)) }))
      .filter((p) => Number.isFinite(p.at))
      .sort((a, b) => a.at - b.at)
      .map((p) => p.id);
    for (let day = from; day <= to; day += 1) {
      if (!days.has(day)) days.set(day, { day, text: body.slice(0, 200), destinations: found });
    }
  }
  const plan = [...days.values()].sort((a, b) => a.day - b.day);
  // A single "Day 1:" line is not a plan.
  return plan.length >= 2 ? plan : [];
}
