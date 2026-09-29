-- My Trip sync (Milestone v0.2, Master Plan §20–21).
-- The app builds trips on the device (guests included) and, once signed in,
-- upserts them with client-generated UUIDs. Destinations are itinerary items.

alter table public.trip_items drop constraint if exists trip_items_item_type_check;
alter table public.trip_items add constraint trip_items_item_type_check
  check (item_type in ('destination', 'place', 'listing', 'activity', 'article', 'note', 'booking', 'transport'));

-- Replaces a trip's days and items in one call, so a sync is atomic and the
-- ownership check happens once (RLS still applies: security invoker).
create or replace function public.sync_trip(trip jsonb, days jsonb, items jsonb)
returns void language plpgsql security invoker set search_path = public as $$
declare tid uuid := (trip ->> 'id')::uuid;
begin
  if auth.uid() is null then raise exception 'not signed in' using errcode = '42501'; end if;
  if (trip ->> 'user_id')::uuid is distinct from auth.uid() then
    raise exception 'trip must belong to the caller' using errcode = '42501';
  end if;
  insert into public.trips (id, user_id, title, start_date, end_date, travelers_adults, travelers_children, notes)
  select tid, auth.uid(), coalesce(trip ->> 'title', 'My Morocco trip'), (trip ->> 'start_date')::date,
         (trip ->> 'end_date')::date, (trip ->> 'travelers_adults')::smallint,
         (trip ->> 'travelers_children')::smallint, trip ->> 'notes'
  on conflict (id) do update set title = excluded.title, start_date = excluded.start_date,
    end_date = excluded.end_date, travelers_adults = excluded.travelers_adults,
    travelers_children = excluded.travelers_children, notes = excluded.notes;
  -- RLS makes the conflict-update a no-op for someone else's trip; refuse loudly instead.
  if not public.owns_trip(tid) then raise exception 'trip belongs to another user' using errcode = '42501'; end if;

  delete from public.trip_items where trip_id = tid;
  delete from public.trip_days where trip_id = tid;
  insert into public.trip_days (id, trip_id, day_number, date)
  select (d ->> 'id')::uuid, tid, (d ->> 'day_number')::smallint, (d ->> 'date')::date
  from jsonb_array_elements(days) d;
  insert into public.trip_items (id, trip_id, trip_day_id, item_type, ref_id, title, position)
  select (i ->> 'id')::uuid, tid, nullif(i ->> 'trip_day_id', '')::uuid, i ->> 'item_type', i ->> 'ref_id',
         i ->> 'title', coalesce((i ->> 'position')::integer, 0)
  from jsonb_array_elements(items) i;
end;
$$;

revoke all on function public.sync_trip(jsonb, jsonb, jsonb) from public, anon;
grant execute on function public.sync_trip(jsonb, jsonb, jsonb) to authenticated;
