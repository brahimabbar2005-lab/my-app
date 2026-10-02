/**
 * My Trip — pure state and operations (Master Plan §20–21).
 *
 * No React, no storage: every function takes the current state and returns
 * the next one, so the rules are unit-tested (test/trip-model.test.ts) and
 * the same shapes map 1:1 onto the Supabase tables (trips, trip_days,
 * trip_items, saved_places) via `toSupabaseRows`.
 */

export const MAX_DAYS = 30;

export type TripItemType = 'destination' | 'listing' | 'activity' | 'article' | 'note';
export type SavedRefType = 'destination' | 'listing' | 'article' | 'place';

export interface TripItem {
  id: string;
  type: TripItemType;
  refId: string | null;
  title: string;
  /** 1-based day, or null for "ideas" not yet placed on a day. */
  day: number | null;
  position: number;
  createdAt: string;
}

export interface Trip {
  id: string;
  title: string;
  startDate: string | null;
  dayCount: number;
  adults: number;
  children: number;
  notes: string;
  items: TripItem[];
  createdAt: string;
  updatedAt: string;
}

export interface SavedPlace {
  refType: SavedRefType;
  refId: string;
  title: string;
  createdAt: string;
}

export interface TripState {
  trip: Trip | null;
  saved: SavedPlace[];
}

export const EMPTY_STATE: TripState = { trip: null, saved: [] };

export interface NewItem {
  type: TripItemType;
  refId?: string | null;
  title: string;
  day?: number | null;
}

type Ids = { id: () => string; now: () => string };

const clampDays = (n: number) => Math.min(MAX_DAYS, Math.max(1, Math.round(n)));
const clampPeople = (n: number) => Math.min(50, Math.max(0, Math.round(n)));

export function createTrip(state: TripState, ids: Ids, init: Partial<Pick<Trip, 'title' | 'dayCount'>> = {}): TripState {
  if (state.trip) return state;
  const now = ids.now();
  return {
    ...state,
    trip: {
      id: ids.id(),
      title: init.title?.trim() || '',
      startDate: null,
      dayCount: clampDays(init.dayCount ?? 3),
      adults: 2,
      children: 0,
      notes: '',
      items: [],
      createdAt: now,
      updatedAt: now,
    },
  };
}

function touch(trip: Trip, ids: Ids, patch: Partial<Trip>): Trip {
  return { ...trip, ...patch, updatedAt: ids.now() };
}

/** Items in itinerary order: day 1…n, then ideas; by position within each. */
export function orderedItems(trip: Trip): TripItem[] {
  const dayKey = (d: number | null) => (d === null ? Number.MAX_SAFE_INTEGER : d);
  return [...trip.items].sort((a, b) => dayKey(a.day) - dayKey(b.day) || a.position - b.position);
}

export function itemsForDay(trip: Trip, day: number | null): TripItem[] {
  return orderedItems(trip).filter((i) => i.day === day);
}

function renumber(items: TripItem[]): TripItem[] {
  const counters = new Map<number | null, number>();
  return items.map((item) => {
    const next = counters.get(item.day) ?? 0;
    counters.set(item.day, next + 1);
    return item.position === next ? item : { ...item, position: next };
  });
}

export function hasItem(trip: Trip | null, type: TripItemType, refId: string): boolean {
  return !!trip?.items.some((i) => i.type === type && i.refId === refId);
}

/** Adds an item (creating the trip if needed). The same place is never added twice. */
export function addItem(state: TripState, ids: Ids, item: NewItem): TripState {
  const withTrip = state.trip ? state : createTrip(state, ids);
  const trip = withTrip.trip!;
  if (item.refId && hasItem(trip, item.type, item.refId)) return withTrip;
  const day = item.day == null ? null : Math.min(trip.dayCount, Math.max(1, item.day));
  const position = trip.items.filter((i) => i.day === day).length;
  const created: TripItem = {
    id: ids.id(),
    type: item.type,
    refId: item.refId ?? null,
    title: item.title.trim().slice(0, 200) || '—',
    day,
    position,
    createdAt: ids.now(),
  };
  return { ...withTrip, trip: touch(trip, ids, { items: [...trip.items, created] }) };
}

export function removeItem(state: TripState, ids: Ids, itemId: string): TripState {
  if (!state.trip) return state;
  const items = renumber(orderedItems(state.trip).filter((i) => i.id !== itemId));
  return { ...state, trip: touch(state.trip, ids, { items }) };
}

export function setItemDay(state: TripState, ids: Ids, itemId: string, day: number | null): TripState {
  if (!state.trip) return state;
  const target = day == null ? null : Math.min(state.trip.dayCount, Math.max(1, day));
  const others = orderedItems(state.trip).filter((i) => i.id !== itemId);
  const item = state.trip.items.find((i) => i.id === itemId);
  if (!item) return state;
  const moved = { ...item, day: target, position: others.filter((i) => i.day === target).length };
  return { ...state, trip: touch(state.trip, ids, { items: renumber(orderedItems({ ...state.trip, items: [...others, moved] })) }) };
}

/**
 * Moves an item one step up or down the itinerary. Crossing the start or end
 * of a day moves it into the neighbouring day, so up/down buttons alone can
 * rearrange a whole trip (no drag-and-drop needed).
 */
export function moveItem(state: TripState, ids: Ids, itemId: string, direction: -1 | 1): TripState {
  const trip = state.trip;
  if (!trip) return state;
  const item = trip.items.find((i) => i.id === itemId);
  if (!item || item.day === null) return state;
  const sameDay = itemsForDay(trip, item.day);
  const index = sameDay.findIndex((i) => i.id === itemId);
  const swapWith = sameDay[index + direction];

  if (swapWith) {
    const items = trip.items.map((i) =>
      i.id === item.id ? { ...i, position: swapWith.position } : i.id === swapWith.id ? { ...i, position: item.position } : i,
    );
    return { ...state, trip: touch(trip, ids, { items }) };
  }
  const nextDay = item.day + direction;
  if (nextDay < 1 || nextDay > trip.dayCount) return state;
  // Entering the previous day at its end, or the next day at its start.
  const others = trip.items.filter((i) => i.id !== itemId);
  const moved: TripItem = { ...item, day: nextDay, position: direction === -1 ? Number.MAX_SAFE_INTEGER : -1 };
  return { ...state, trip: touch(trip, ids, { items: renumber(orderedItems({ ...trip, items: [...others, moved] })) }) };
}

/** Changing the number of days never loses items: those beyond the end become ideas. */
export function setDayCount(state: TripState, ids: Ids, dayCount: number): TripState {
  if (!state.trip) return state;
  const count = clampDays(dayCount);
  const items = state.trip.items.map((i) => (i.day !== null && i.day > count ? { ...i, day: null } : i));
  return { ...state, trip: touch(state.trip, ids, { dayCount: count, items: renumber(orderedItems({ ...state.trip, items })) }) };
}

export function updateTrip(
  state: TripState,
  ids: Ids,
  patch: Partial<Pick<Trip, 'title' | 'startDate' | 'adults' | 'children' | 'notes'>>,
): TripState {
  if (!state.trip) return state;
  const clean: Partial<Trip> = { ...patch };
  if (patch.title !== undefined) clean.title = patch.title.slice(0, 120);
  if (patch.adults !== undefined) clean.adults = clampPeople(patch.adults);
  if (patch.children !== undefined) clean.children = clampPeople(patch.children);
  if (patch.notes !== undefined) clean.notes = patch.notes.slice(0, 5000);
  if (patch.startDate !== undefined && patch.startDate !== null && !/^\d{4}-\d{2}-\d{2}$/.test(patch.startDate)) {
    delete clean.startDate;
  }
  return { ...state, trip: touch(state.trip, ids, clean) };
}

export function deleteTrip(state: TripState): TripState {
  return { ...state, trip: null };
}

export function isSaved(state: TripState, refType: SavedRefType, refId: string): boolean {
  return state.saved.some((s) => s.refType === refType && s.refId === refId);
}

export function toggleSaved(state: TripState, ids: Ids, place: { refType: SavedRefType; refId: string; title: string }): TripState {
  if (isSaved(state, place.refType, place.refId)) {
    return { ...state, saved: state.saved.filter((s) => !(s.refType === place.refType && s.refId === place.refId)) };
  }
  return { ...state, saved: [...state.saved, { ...place, createdAt: ids.now() }] };
}

/** Plain-text itinerary for the system share sheet. */
export function tripToText(trip: Trip, labels: { day: (n: number) => string; ideas: string; untitled: string }): string {
  const lines = [trip.title || labels.untitled];
  for (let day = 1; day <= trip.dayCount; day++) {
    const items = itemsForDay(trip, day);
    if (!items.length) continue;
    lines.push('', labels.day(day));
    for (const item of items) lines.push(`• ${item.title}`);
  }
  const ideas = itemsForDay(trip, null);
  if (ideas.length) {
    lines.push('', labels.ideas);
    for (const item of ideas) lines.push(`• ${item.title}`);
  }
  if (trip.notes.trim()) lines.push('', trip.notes.trim());
  lines.push('', 'comemorocco.com');
  return lines.join('\n');
}

/** A compact summary the AI receives as controlled trip context (§20). */
export function tripContext(trip: Trip | null): { day_count: number; destinations: string[]; start_date: string | null } | null {
  if (!trip) return null;
  const destinations = orderedItems(trip)
    .filter((i) => i.type === 'destination' && i.refId)
    .map((i) => i.title);
  return { day_count: trip.dayCount, destinations: [...new Set(destinations)].slice(0, 12), start_date: trip.startDate };
}

// ---------------------------------------------------------------- Supabase mapping
export const DB_ITEM_TYPE: Record<TripItemType, string> = {
  destination: 'destination',
  listing: 'listing',
  activity: 'activity',
  article: 'article',
  note: 'note',
};

/** Rows for public.trips / trip_days / trip_items (column names as in the migration). */
export function toSupabaseRows(trip: Trip, userId: string) {
  const dayIds = new Map<number, string>();
  const days = Array.from({ length: trip.dayCount }, (_, i) => {
    const id = deterministicUuid(`${trip.id}:day:${i + 1}`);
    dayIds.set(i + 1, id);
    return { id, trip_id: trip.id, day_number: i + 1, date: addDays(trip.startDate, i) };
  });
  return {
    trip: {
      id: trip.id,
      user_id: userId,
      title: trip.title || 'My Morocco trip',
      start_date: trip.startDate,
      end_date: addDays(trip.startDate, trip.dayCount - 1),
      travelers_adults: trip.adults,
      travelers_children: trip.children,
      notes: trip.notes || null,
    },
    days,
    items: orderedItems(trip).map((i) => ({
      id: i.id,
      trip_id: trip.id,
      trip_day_id: i.day === null ? null : (dayIds.get(i.day) ?? null),
      item_type: DB_ITEM_TYPE[i.type],
      ref_id: i.refId,
      title: i.title,
      position: i.position,
    })),
  };
}

function addDays(start: string | null, offset: number): string | null {
  if (!start) return null;
  const d = new Date(`${start}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + offset);
  return d.toISOString().slice(0, 10);
}

/** Stable UUID-shaped id derived from a string (FNV-1a based; not cryptographic). */
export function deterministicUuid(input: string): string {
  let hex = '';
  for (let round = 0; hex.length < 32; round++) {
    let h = 0x811c9dc5 ^ round;
    for (let i = 0; i < input.length; i++) {
      h ^= input.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    hex += h.toString(16).padStart(8, '0');
  }
  return formatUuid(hex.slice(0, 32));
}

/** Formats 32 hex chars as a version-4-shaped UUID. */
export function formatUuid(hex32: string): string {
  const h = hex32.padEnd(32, '0').slice(0, 32).split('');
  h[12] = '4';
  h[16] = ((parseInt(h[16] ?? '8', 16) & 0x3) | 0x8).toString(16);
  const s = h.join('');
  return `${s.slice(0, 8)}-${s.slice(8, 12)}-${s.slice(12, 16)}-${s.slice(16, 20)}-${s.slice(20, 32)}`;
}

export interface PlanToApply {
  day: number;
  text: string;
  destinations: { id: string; title: string }[];
}

/**
 * Saves a day-by-day plan (from an AI answer) into the trip: enough days for
 * the plan, each day's plan as a note on that day, and each city once, on the
 * first day it appears. Existing items stay; tapping twice adds nothing new
 * except the notes, which the screen prevents by disabling the button.
 */
export function applyPlan(state: TripState, ids: Ids, plan: PlanToApply[]): TripState {
  if (!plan.length) return state;
  const lastDay = Math.max(...plan.map((p) => p.day));
  let next = state.trip ? state : createTrip(state, ids, { dayCount: lastDay });
  if (next.trip!.dayCount < lastDay) next = setDayCount(next, ids, lastDay);
  for (const day of plan) {
    for (const place of day.destinations) {
      next = addItem(next, ids, { type: 'destination', refId: place.id, title: place.title, day: day.day });
    }
    next = addItem(next, ids, { type: 'note', title: day.text, day: day.day });
  }
  return next;
}
