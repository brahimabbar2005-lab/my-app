-- Admin catalogue (v0.4): admins add and edit stays (hotels, riads, hostels,
-- camps…), tours and other offers from the app. Partner (affiliate) links
-- stay private in affiliate_links and are opened through the platform
-- worker's /go redirect; a direct booking page (the riad's own site) is
-- public in listings.website_url and opened as is.

alter table public.listings
  add column if not exists subtype text check (subtype in (
    'hotel', 'riad', 'hostel', 'guesthouse', 'camp', 'apartment', 'villa',
    'tour', 'day_trip', 'activity', 'class', 'car', 'transfer', 'driver')),
  add column if not exists image_url text check (image_url ~ '^https://'),
  add column if not exists website_url text check (website_url ~ '^https://');

-- Admins see drafts and archived offers too.
create policy "admins read all listings" on public.listings for select using (public.is_admin());

create or replace function public.admin_require()
returns void language plpgsql stable security definer set search_path = public as $$
begin
  -- App admins, or trusted database access (SQL Editor, service role).
  if not (public.is_admin()
          or coalesce(nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role', '') not in ('anon', 'authenticated')) then
    raise exception 'admins only' using errcode = '42501';
  end if;
end;
$$;

-- Every offer with its private partner link, for the admin screens.
create or replace function public.admin_listings()
returns table (
  id text, kind text, category text, subtype text, title text, subtitle text, description text,
  destination_id text, partner_name text, status text, price_from_minor integer, currency text,
  image_url text, website_url text, partner_url text, updated_at timestamptz
)
language plpgsql stable security definer set search_path = public as $$
begin
  perform public.admin_require();
  return query
  select l.id, l.kind, l.category, l.subtype, l.title, l.subtitle, l.description, l.destination_id,
         l.partner_name, l.status, l.price_from_minor, l.currency, l.image_url, l.website_url,
         a.url, l.updated_at
  from public.listings l
  left join public.affiliate_links a on a.listing_id = l.id
  order by l.updated_at desc;
end;
$$;

-- Create or update one offer. `p` holds the listing fields plus link_url and
-- link_is_partner. New offers get an ADM- id and start as drafts unless
-- status says otherwise.
create or replace function public.admin_save_listing(p jsonb)
returns text language plpgsql security definer set search_path = public as $$
declare
  lid text := coalesce(nullif(p ->> 'id', ''), 'ADM-' || substr(md5(gen_random_uuid()::text), 1, 10));
  link text := nullif(trim(p ->> 'link_url'), '');
  is_partner boolean := coalesce((p ->> 'link_is_partner')::boolean, false);
  price integer := nullif(p ->> 'price_from_minor', '')::integer;
begin
  perform public.admin_require();
  if coalesce(trim(p ->> 'title'), '') = '' then
    raise exception 'a title is required' using errcode = '22023';
  end if;
  if link is not null and link !~ '^https://' then
    raise exception 'links must start with https://' using errcode = '22023';
  end if;

  insert into public.listings (
    id, kind, category, subtype, title, subtitle, description, destination_id, partner_name,
    status, price_from_minor, currency, image_url, website_url)
  values (
    lid, 'direct', p ->> 'category', nullif(p ->> 'subtype', ''), trim(p ->> 'title'),
    nullif(trim(p ->> 'subtitle'), ''), nullif(trim(p ->> 'description'), ''),
    nullif(p ->> 'destination_id', ''), nullif(trim(p ->> 'partner_name'), ''),
    coalesce(nullif(p ->> 'status', ''), 'draft'), price,
    case when price is null then null else coalesce(nullif(p ->> 'currency', ''), 'MAD') end,
    nullif(trim(p ->> 'image_url'), ''), case when is_partner then null else link end)
  on conflict (id) do update set
    category = excluded.category, subtype = excluded.subtype, title = excluded.title,
    subtitle = excluded.subtitle, description = excluded.description,
    destination_id = excluded.destination_id, partner_name = excluded.partner_name,
    status = excluded.status, price_from_minor = excluded.price_from_minor,
    currency = excluded.currency, image_url = excluded.image_url,
    website_url = excluded.website_url, updated_at = now();

  if is_partner and link is not null then
    insert into public.affiliate_links (listing_id, partner, url)
    values (lid, coalesce(nullif(trim(p ->> 'partner_name'), ''), 'partner'), link)
    on conflict (listing_id) do update set url = excluded.url, partner = excluded.partner,
      active = true, updated_at = now();
  else
    -- A direct link or none: an earlier partner link must not keep redirecting.
    delete from public.affiliate_links where listing_id = lid;
  end if;

  insert into public.audit_log (actor_id, action, target_type, target_id, data)
  values (auth.uid(), 'catalog.save_listing', 'listing', lid,
          jsonb_build_object('status', p ->> 'status', 'category', p ->> 'category'));
  return lid;
end;
$$;

revoke all on function public.admin_require(), public.admin_listings(), public.admin_save_listing(jsonb) from public, anon;
grant execute on function public.admin_require(), public.admin_listings(), public.admin_save_listing(jsonb) to authenticated;
