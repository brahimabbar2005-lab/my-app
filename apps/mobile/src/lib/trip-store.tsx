/**
 * My Trip store (Master Plan §20–21, §34).
 *
 * Local-first: the trip and saved places live on the device, so guests can
 * plan and everything works offline. When Supabase is configured and the
 * traveller is signed in, every change is also written through
 * `sync_trip` (RLS-checked, atomic); on first sign-in a device trip is
 * uploaded, or the account's trip is downloaded if the device has none.
 */
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { track } from './analytics';
import { useAuth } from './auth';
import { randomId } from './ids';
import { readJson, writeJson } from './storage';
import { supabase } from './supabase';
import * as model from './trip-model';

const KEY = 'trip:v1';

const ids = {
  id: () => model.formatUuid(randomId(16)),
  now: () => new Date().toISOString(),
};

export type SyncStatus = 'local' | 'syncing' | 'synced' | 'error';

interface TripStore {
  ready: boolean;
  state: model.TripState;
  sync: SyncStatus;
  createTrip: (init?: { title?: string; dayCount?: number }) => void;
  addItem: (item: model.NewItem) => void;
  removeItem: (id: string) => void;
  moveItem: (id: string, direction: -1 | 1) => void;
  setItemDay: (id: string, day: number | null) => void;
  setDayCount: (n: number) => void;
  applyPlan: (plan: model.PlanToApply[]) => void;
  updateTrip: (patch: Parameters<typeof model.updateTrip>[2]) => void;
  deleteTrip: () => void;
  toggleSaved: (place: { refType: model.SavedRefType; refId: string; title: string }) => void;
  isSaved: (refType: model.SavedRefType, refId: string) => boolean;
  hasItem: (type: model.TripItemType, refId: string) => boolean;
}

const TripContext = createContext<TripStore | null>(null);

export function TripProvider({ children }: { children: ReactNode }) {
  const { userId } = useAuth();
  const [state, setState] = useState<model.TripState>(model.EMPTY_STATE);
  const [ready, setReady] = useState(false);
  const [sync, setSync] = useState<SyncStatus>('local');
  const pushTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    readJson<model.TripState>(KEY, model.EMPTY_STATE).then((stored) => {
      setState({ trip: stored.trip ?? null, saved: Array.isArray(stored.saved) ? stored.saved : [] });
      setReady(true);
    });
  }, []);

  const push = useCallback(
    (trip: model.Trip | null) => {
      if (!supabase || !userId || !trip) return;
      if (pushTimer.current) clearTimeout(pushTimer.current);
      pushTimer.current = setTimeout(async () => {
        setSync('syncing');
        const rows = model.toSupabaseRows(trip, userId);
        const { error } = await supabase!.rpc('sync_trip', { trip: rows.trip, days: rows.days, items: rows.items });
        setSync(error ? 'error' : 'synced');
      }, 800);
    },
    [userId],
  );

  // First sign-in on this device: upload the device trip, or adopt the account's.
  useEffect(() => {
    if (!ready || !supabase || !userId) return;
    let alive = true;
    (async () => {
      if (state.trip) {
        push(state.trip);
        return;
      }
      const { data } = await supabase!
        .from('trips')
        .select('id,title,start_date,travelers_adults,travelers_children,notes,created_at,updated_at,trip_days(id,day_number),trip_items(id,trip_day_id,item_type,ref_id,title,position,created_at)')
        .order('updated_at', { ascending: false })
        .limit(1)
        .maybeSingle();
      if (!alive || !data) return;
      setState((current) => (current.trip ? current : { ...current, trip: fromServer(data) }));
      setSync('synced');
    })();
    return () => {
      alive = false;
    };
    // Only when the signed-in user changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, userId]);

  // Updaters stay pure; persistence and sync react to the committed state.
  const apply = useCallback((fn: (s: model.TripState) => model.TripState) => setState(fn), []);

  const lastTrip = useRef<model.Trip | null | undefined>(undefined);
  useEffect(() => {
    if (!ready) return;
    if (lastTrip.current === undefined) {
      lastTrip.current = state.trip; // initial load — nothing to write
      return;
    }
    writeJson(KEY, state);
    if (state.trip !== lastTrip.current) push(state.trip);
    lastTrip.current = state.trip;
  }, [ready, state, push]);

  const store = useMemo<TripStore>(
    () => ({
      ready,
      state,
      sync: userId && supabase ? sync : 'local',
      createTrip: (init) => {
        if (!state.trip) track('trip_created');
        apply((s) => model.createTrip(s, ids, init));
      },
      addItem: (item) => {
        if (!state.trip) track('trip_created');
        if (!(item.refId && model.hasItem(state.trip, item.type, item.refId))) {
          track('trip_item_added', { properties: { type: item.type, ref: item.refId ?? null } });
        }
        apply((s) => model.addItem(s, ids, item));
      },
      removeItem: (id) => apply((s) => model.removeItem(s, ids, id)),
      moveItem: (id, direction) => apply((s) => model.moveItem(s, ids, id, direction)),
      setItemDay: (id, day) => apply((s) => model.setItemDay(s, ids, id, day)),
      setDayCount: (n) => apply((s) => model.setDayCount(s, ids, n)),
      applyPlan: (plan) => {
        if (!state.trip) track('trip_created');
        track('trip_item_added', { properties: { type: 'ai_plan', days: plan.length } });
        apply((s) => model.applyPlan(s, ids, plan));
      },
      updateTrip: (patch) => apply((s) => model.updateTrip(s, ids, patch)),
      deleteTrip: () => {
        const tripId = state.trip?.id;
        apply(model.deleteTrip);
        if (tripId && supabase && userId) supabase.from('trips').delete().eq('id', tripId).then(() => {});
      },
      toggleSaved: (place) => apply((s) => model.toggleSaved(s, ids, place)),
      isSaved: (refType, refId) => model.isSaved(state, refType, refId),
      hasItem: (type, refId) => model.hasItem(state.trip, type, refId),
    }),
    [ready, state, sync, userId, apply],
  );

  return <TripContext.Provider value={store}>{children}</TripContext.Provider>;
}

export function useTrip(): TripStore {
  const ctx = useContext(TripContext);
  if (!ctx) throw new Error('useTrip must be used inside TripProvider');
  return ctx;
}

interface ServerTrip {
  id: string;
  title: string;
  start_date: string | null;
  travelers_adults: number | null;
  travelers_children: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  trip_days: { id: string; day_number: number }[];
  trip_items: {
    id: string;
    trip_day_id: string | null;
    item_type: string;
    ref_id: string | null;
    title: string | null;
    position: number;
    created_at: string;
  }[];
}

function fromServer(row: ServerTrip): model.Trip {
  const dayNumber = new Map(row.trip_days.map((d) => [d.id, d.day_number]));
  const known: model.TripItemType[] = ['destination', 'listing', 'activity', 'article', 'note'];
  return {
    id: row.id,
    title: row.title === 'My Morocco trip' ? '' : row.title,
    startDate: row.start_date,
    dayCount: Math.max(1, row.trip_days.length || 1),
    adults: row.travelers_adults ?? 2,
    children: row.travelers_children ?? 0,
    notes: row.notes ?? '',
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    items: row.trip_items
      .filter((i) => (known as string[]).includes(i.item_type))
      .map((i) => ({
        id: i.id,
        type: i.item_type as model.TripItemType,
        refId: i.ref_id,
        title: i.title ?? '—',
        day: i.trip_day_id ? (dayNumber.get(i.trip_day_id) ?? null) : null,
        position: i.position,
        createdAt: i.created_at,
      })),
  };
}
