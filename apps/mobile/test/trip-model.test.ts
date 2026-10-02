import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  addItem,
  applyPlan,
  createTrip,
  deterministicUuid,
  EMPTY_STATE,
  itemsForDay,
  moveItem,
  removeItem,
  setDayCount,
  setItemDay,
  toggleSaved,
  toSupabaseRows,
  tripContext,
  tripToText,
  updateTrip,
  type TripState,
} from '../src/lib/trip-model';

function idsFactory() {
  let n = 0;
  return { id: () => deterministicUuid(`id-${++n}`), now: () => '2026-09-29T10:00:00.000Z' };
}

const titles = (s: TripState, day: number | null) => itemsForDay(s.trip!, day).map((i) => i.title);

function sample() {
  const ids = idsFactory();
  let s = createTrip(EMPTY_STATE, ids, { dayCount: 3 });
  s = addItem(s, ids, { type: 'destination', refId: 'marrakech', title: 'Marrakech', day: 1 });
  s = addItem(s, ids, { type: 'listing', refId: 'GYG-018', title: 'Medina tour', day: 1 });
  s = addItem(s, ids, { type: 'listing', refId: 'GYG-008', title: 'Desert safari', day: 2 });
  s = addItem(s, ids, { type: 'article', refId: 'wp-1', title: 'What to wear' });
  return { s, ids };
}

describe('trip model', () => {
  it('adds items to days and ideas, creating the trip on first add', () => {
    const ids = idsFactory();
    const s = addItem(EMPTY_STATE, ids, { type: 'destination', refId: 'fes', title: 'Fes', day: 9 });
    expect(s.trip).not.toBeNull();
    expect(s.trip!.dayCount).toBe(3);
    expect(titles(s, 3)).toEqual(['Fes']); // clamped to the last day
    const { s: t } = sample();
    expect(titles(t, 1)).toEqual(['Marrakech', 'Medina tour']);
    expect(titles(t, null)).toEqual(['What to wear']);
  });

  it('never adds the same place twice', () => {
    const { s, ids } = sample();
    const again = addItem(s, ids, { type: 'listing', refId: 'GYG-008', title: 'Desert safari', day: 3 });
    expect(again).toBe(s);
  });

  it('moves items within a day and across day boundaries', () => {
    const { s, ids } = sample();
    const medina = s.trip!.items.find((i) => i.title === 'Medina tour')!;
    let t = moveItem(s, ids, medina.id, -1);
    expect(titles(t, 1)).toEqual(['Medina tour', 'Marrakech']);
    t = moveItem(t, ids, medina.id, -1); // already first on day 1, no day 0
    expect(titles(t, 1)).toEqual(['Medina tour', 'Marrakech']);
    const marrakech = s.trip!.items.find((i) => i.title === 'Marrakech')!;
    t = moveItem(t, ids, marrakech.id, 1); // last on day 1 → first on day 2
    expect(titles(t, 1)).toEqual(['Medina tour']);
    expect(titles(t, 2)).toEqual(['Marrakech', 'Desert safari']);
    const safari = t.trip!.items.find((i) => i.title === 'Desert safari')!;
    t = moveItem(t, ids, safari.id, 1); // last on day 2 → first on day 3
    expect(titles(t, 3)).toEqual(['Desert safari']);
  });

  it('keeps positions contiguous after removals and day changes', () => {
    const { s, ids } = sample();
    const first = itemsForDay(s.trip!, 1)[0]!;
    const t = removeItem(s, ids, first.id);
    expect(itemsForDay(t.trip!, 1).map((i) => i.position)).toEqual([0]);
    const idea = itemsForDay(t.trip!, null)[0]!;
    const u = setItemDay(t, ids, idea.id, 1);
    expect(itemsForDay(u.trip!, 1).map((i) => [i.title, i.position])).toEqual([
      ['Medina tour', 0],
      ['What to wear', 1],
    ]);
  });

  it('shrinking the trip turns later days into ideas instead of deleting them', () => {
    const { s, ids } = sample();
    const t = setDayCount(s, ids, 1);
    expect(t.trip!.dayCount).toBe(1);
    expect(titles(t, null)).toContain('Desert safari');
    expect(t.trip!.items).toHaveLength(4);
    expect(setDayCount(s, ids, 999).trip!.dayCount).toBe(30);
    expect(setDayCount(s, ids, 0).trip!.dayCount).toBe(1);
  });

  it('validates trip details', () => {
    const { s, ids } = sample();
    const t = updateTrip(s, ids, { adults: -3, children: 99, startDate: 'next friday', title: 'x'.repeat(500) });
    expect(t.trip!.adults).toBe(0);
    expect(t.trip!.children).toBe(50);
    expect(t.trip!.startDate).toBeNull();
    expect(t.trip!.title).toHaveLength(120);
  });

  it('toggles saved places', () => {
    const ids = idsFactory();
    const place = { refType: 'destination' as const, refId: 'fes', title: 'Fes' };
    const s = toggleSaved(EMPTY_STATE, ids, place);
    expect(s.saved).toHaveLength(1);
    expect(toggleSaved(s, ids, place).saved).toHaveLength(0);
  });

  it('shares as readable text and gives the AI a compact context', () => {
    const { s } = sample();
    const text = tripToText(s.trip!, { day: (n) => `Day ${n}`, ideas: 'Ideas', untitled: 'My trip' });
    expect(text).toContain('Day 1\n• Marrakech\n• Medina tour');
    expect(text).toContain('Ideas\n• What to wear');
    expect(tripContext(s.trip)).toEqual({ day_count: 3, destinations: ['Marrakech'], start_date: null });
    expect(tripContext(null)).toBeNull();
  });
});

describe('Supabase mapping', () => {
  const migration = readFileSync(
    join(__dirname, '../../../supabase/migrations/20260929000001_foundation.sql'),
    'utf8',
  );
  const columns = (table: string) => {
    const body = migration.split(`create table public.${table} (`)[1]!.split('\n);')[0]!;
    return body
      .split('\n')
      .map((l) => l.trim().split(/\s+/)[0]!)
      .filter((c) => c && !['check', 'unique', 'primary'].includes(c) && !c.startsWith('--'));
  };

  it('produces rows whose columns exist in the migration', () => {
    const { s } = sample();
    const trip = updateTrip(s, idsFactory(), { startDate: '2026-10-01' }).trip!;
    const rows = toSupabaseRows(trip, '00000000-0000-0000-0000-00000000000a');
    for (const key of Object.keys(rows.trip)) expect(columns('trips')).toContain(key);
    for (const key of Object.keys(rows.days[0]!)) expect(columns('trip_days')).toContain(key);
    for (const key of Object.keys(rows.items[0]!)) expect(columns('trip_items')).toContain(key);
    expect(rows.trip.end_date).toBe('2026-10-03');
    expect(rows.days.map((d) => d.date)).toEqual(['2026-10-01', '2026-10-02', '2026-10-03']);
    const safari = rows.items.find((i) => i.ref_id === 'GYG-008')!;
    expect(safari.trip_day_id).toBe(rows.days[1]!.id);
    expect(rows.items.find((i) => i.ref_id === 'wp-1')!.trip_day_id).toBeNull();
  });

  it('generates UUID-shaped ids the database accepts', () => {
    expect(deterministicUuid('x')).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(deterministicUuid('x')).toBe(deterministicUuid('x'));
    expect(deterministicUuid('x')).not.toBe(deterministicUuid('y'));
  });
});

describe('applyPlan', () => {
  it('adds days, a note per day and each city once', () => {
    let n = 0;
    const ids = { id: () => `id-${(n += 1)}`, now: () => '2026-10-02T00:00:00.000Z' };
    const plan = [
      { day: 1, text: 'Marrakech — medina', destinations: [{ id: 'marrakech', title: 'Marrakech' }] },
      { day: 2, text: 'Marrakech — gardens', destinations: [{ id: 'marrakech', title: 'Marrakech' }] },
      { day: 3, text: 'Atlas foothills', destinations: [] },
    ];
    const state = applyPlan(EMPTY_STATE, ids, plan);
    expect(state.trip!.dayCount).toBe(3);
    expect(state.trip!.items.filter((i) => i.type === 'destination').map((i) => [i.refId, i.day])).toEqual([['marrakech', 1]]);
    expect(state.trip!.items.filter((i) => i.type === 'note').map((i) => [i.day, i.title])).toEqual([
      [1, 'Marrakech — medina'],
      [2, 'Marrakech — gardens'],
      [3, 'Atlas foothills'],
    ]);
    expect(applyPlan(state, ids, []).trip).toBe(state.trip);
  });
});
