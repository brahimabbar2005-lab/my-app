-- ComeMorocco platform — foundation schema (Master Plan §20, §43–44).
--
-- Principles:
--   * RLS is enabled on every table before any feature depends on it.
--   * Owner data (trips, saved places, AI history…) is visible to its owner only.
--   * Affiliate links, clicks, conversions and commissions are service-role only:
--     no policy exists for anon/authenticated, and table privileges are revoked.
--   * Moderation fields (status) cannot be changed by authors — a trigger resets
--     them unless the caller is an admin or the service role.
--   * Time-sensitive facts carry `source` and `last_verified`.
--   * Money is stored in minor units (integer) with an ISO currency.

set check_function_bodies = off;

-- ---------------------------------------------------------------- helpers
create table public.admin_users (
  user_id uuid primary key references auth.users (id) on delete cascade,
  created_at timestamptz not null default now()
);

create or replace function public.is_admin()
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.admin_users where user_id = auth.uid());
$$;

create or replace function public.is_service_role()
returns boolean language sql stable as $$
  select coalesce(current_setting('request.jwt.claims', true)::jsonb ->> 'role', '') = 'service_role'
      or current_user in ('service_role', 'postgres', 'supabase_admin');
$$;

create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------- people
create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text check (char_length(display_name) <= 60),
  avatar_url text,
  status text not null default 'active' check (status in ('active', 'suspended')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.user_preferences (
  user_id uuid primary key references auth.users (id) on delete cascade,
  locale text check (locale in ('en', 'fr', 'ar', 'es')),
  currency text not null default 'MAD' check (char_length(currency) = 3),
  trip_stage text check (trip_stage in ('dreaming', 'planning', 'in_morocco')),
  interests text[] not null default '{}',
  travel_style text,
  budget text,
  food_preferences text[] not null default '{}',
  activity_preferences text[] not null default '{}',
  accessibility text[] not null default '{}',
  notification_preferences jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table public.user_suspensions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  reason text not null,
  starts_at timestamptz not null default now(),
  ends_at timestamptz,
  created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now()
);

create or replace function public.is_suspended(uid uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.user_suspensions
    where user_id = uid and starts_at <= now() and (ends_at is null or ends_at > now())
  );
$$;

-- New auth user → profile + preferences rows.
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id) values (new.id) on conflict do nothing;
  insert into public.user_preferences (user_id) values (new.id) on conflict do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------- catalog
create table public.destinations (
  id text primary key check (id ~ '^[a-z0-9-]+$'),
  name jsonb not null,
  region text,
  lat double precision,
  lng double precision,
  tagline text,
  hue text,
  guide_url text,
  created_at timestamptz not null default now()
);

create table public.categories (
  id text primary key,
  name jsonb not null,
  parent_id text references public.categories (id)
);

create table public.places (
  id uuid primary key default gen_random_uuid(),
  destination_id text references public.destinations (id),
  category_id text references public.categories (id),
  name text not null,
  lat double precision,
  lng double precision,
  address text,
  source text,
  created_at timestamptz not null default now()
);

create table public.providers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  kind text not null check (kind in ('stay', 'experience', 'car', 'transfer', 'driver', 'guide', 'other')),
  status text not null default 'pending' check (status in ('pending', 'active', 'suspended')),
  country text not null default 'MA',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.provider_users (
  provider_id uuid not null references public.providers (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  role text not null default 'owner' check (role in ('owner', 'staff')),
  primary key (provider_id, user_id)
);

create or replace function public.is_provider_member(pid uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.provider_users where provider_id = pid and user_id = auth.uid());
$$;

create table public.provider_documents (
  id uuid primary key default gen_random_uuid(),
  provider_id uuid not null references public.providers (id) on delete cascade,
  kind text not null,
  storage_path text not null,
  status text not null default 'submitted' check (status in ('submitted', 'approved', 'rejected')),
  created_at timestamptz not null default now()
);

create table public.listings (
  id text primary key check (id ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$'),
  kind text not null check (kind in ('program', 'activity', 'direct')),
  category text not null check (category in ('stay', 'experience', 'car', 'transfer', 'driver')),
  title text not null,
  subtitle text,
  description text,
  destination_id text references public.destinations (id),
  provider_id uuid references public.providers (id) on delete set null,
  partner_name text,
  status text not null default 'draft' check (status in ('draft', 'published', 'archived')),
  price_from_minor integer check (price_from_minor >= 0),
  currency text check (char_length(currency) = 3),
  rating numeric(2, 1) check (rating between 0 and 5),
  cancellation_info text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.listing_images (
  id uuid primary key default gen_random_uuid(),
  listing_id text not null references public.listings (id) on delete cascade,
  url text not null check (url ~ '^https://'),
  alt text,
  position smallint not null default 0
);

create table public.listing_categories (
  listing_id text not null references public.listings (id) on delete cascade,
  category_id text not null references public.categories (id) on delete cascade,
  primary key (listing_id, category_id)
);

create table public.listing_locations (
  listing_id text primary key references public.listings (id) on delete cascade,
  lat double precision not null,
  lng double precision not null,
  address text
);

create table public.provider_availability (
  id uuid primary key default gen_random_uuid(),
  listing_id text not null references public.listings (id) on delete cascade,
  date date not null,
  capacity integer not null check (capacity >= 0),
  price_minor integer check (price_minor >= 0),
  currency text check (char_length(currency) = 3),
  unique (listing_id, date)
);

create table public.content_items (
  id text primary key,
  source text not null default 'wordpress' check (source in ('wordpress')),
  wordpress_post_id integer,
  canonical_url text not null check (canonical_url ~ '^https://(www\.)?comemorocco\.com/'),
  title text not null,
  excerpt text,
  image_url text,
  categories text[] not null default '{}',
  destination_id text references public.destinations (id),
  topic text,
  updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------- trips
create table public.trips (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  title text not null default 'My Morocco trip' check (char_length(title) <= 120),
  start_date date,
  end_date date,
  travelers_adults smallint check (travelers_adults between 0 and 50),
  travelers_children smallint check (travelers_children between 0 and 50),
  budget text,
  notes text,
  share_token text unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (end_date is null or start_date is null or end_date >= start_date)
);

create table public.trip_days (
  id uuid primary key default gen_random_uuid(),
  trip_id uuid not null references public.trips (id) on delete cascade,
  day_number smallint not null check (day_number between 1 and 90),
  date date,
  destination_id text references public.destinations (id),
  unique (trip_id, day_number)
);

create table public.trip_items (
  id uuid primary key default gen_random_uuid(),
  trip_id uuid not null references public.trips (id) on delete cascade,
  trip_day_id uuid references public.trip_days (id) on delete set null,
  item_type text not null check (item_type in ('place', 'listing', 'activity', 'article', 'note', 'booking', 'transport')),
  ref_id text,
  title text,
  position integer not null default 0,
  notes text,
  created_at timestamptz not null default now()
);

create table public.saved_places (
  user_id uuid not null references auth.users (id) on delete cascade,
  ref_type text not null check (ref_type in ('place', 'listing', 'destination', 'article')),
  ref_id text not null,
  created_at timestamptz not null default now(),
  primary key (user_id, ref_type, ref_id)
);

create or replace function public.owns_trip(tid uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.trips where id = tid and user_id = auth.uid());
$$;

-- ---------------------------------------------------------------- direct bookings (Phase 8+; RLS now)
create table public.bookings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users (id) on delete set null,
  provider_id uuid references public.providers (id) on delete set null,
  status text not null default 'pending'
    check (status in ('pending', 'confirmed', 'declined', 'cancelled', 'completed', 'no_show', 'refunded', 'disputed')),
  booking_code text unique,
  total_minor integer check (total_minor >= 0),
  currency text check (char_length(currency) = 3),
  idempotency_key text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, idempotency_key)
);

create table public.booking_items (
  id uuid primary key default gen_random_uuid(),
  booking_id uuid not null references public.bookings (id) on delete cascade,
  listing_id text references public.listings (id) on delete set null,
  date date,
  quantity integer not null default 1 check (quantity > 0),
  unit_price_minor integer check (unit_price_minor >= 0)
);

create table public.booking_status_history (
  id bigint generated always as identity primary key,
  booking_id uuid not null references public.bookings (id) on delete cascade,
  from_status text,
  to_status text not null,
  changed_by uuid references auth.users (id) on delete set null,
  reason text,
  created_at timestamptz not null default now()
);

create or replace function public.log_booking_status()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if tg_op = 'INSERT' or new.status is distinct from old.status then
    insert into public.booking_status_history (booking_id, from_status, to_status, changed_by)
    values (new.id, case when tg_op = 'UPDATE' then old.status end, new.status, auth.uid());
  end if;
  return new;
end;
$$;

create trigger booking_status_history after insert or update of status on public.bookings
  for each row execute function public.log_booking_status();

-- ---------------------------------------------------------------- affiliate (service role only)
create table public.affiliate_programs (
  id text primary key,
  name text not null,
  category text not null,
  usable boolean not null default true,
  conversion_capability text not null default 'manual'
    check (conversion_capability in ('api', 'webhook', 'report_import', 'manual')),
  created_at timestamptz not null default now()
);

create table public.affiliate_links (
  listing_id text primary key references public.listings (id) on delete cascade,
  program_id text references public.affiliate_programs (id),
  partner text not null,
  url text not null check (url ~ '^https://'),
  active boolean not null default true,
  updated_at timestamptz not null default now()
);

create table public.affiliate_clicks (
  id uuid primary key,
  listing_id text not null,
  program_id text,
  partner text not null,
  source text not null default 'unknown',
  campaign text,
  trip_id text,
  anonymous_id text,
  user_id uuid references auth.users (id) on delete set null,
  platform text,
  country text,
  referrer_host text,
  created_at timestamptz not null default now()
);
create index affiliate_clicks_listing_created on public.affiliate_clicks (listing_id, created_at desc);

create table public.affiliate_conversions (
  id uuid primary key default gen_random_uuid(),
  click_id uuid references public.affiliate_clicks (id) on delete set null,
  program_id text references public.affiliate_programs (id),
  external_ref text not null,
  status text not null default 'reported' check (status in ('reported', 'booked', 'cancelled')),
  amount_minor integer,
  currency text,
  occurred_at timestamptz,
  imported_via text not null check (imported_via in ('api', 'webhook', 'report_import', 'manual')),
  created_at timestamptz not null default now(),
  unique (program_id, external_ref)
);

create table public.affiliate_commissions (
  id uuid primary key default gen_random_uuid(),
  conversion_id uuid not null references public.affiliate_conversions (id) on delete cascade,
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected', 'paid')),
  amount_minor integer not null,
  currency text not null,
  approved_at timestamptz,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------- community + moderation
create table public.community_posts (
  id uuid primary key default gen_random_uuid(),
  author_id uuid not null references auth.users (id) on delete cascade,
  kind text not null default 'post' check (kind in ('post', 'question', 'trip_report')),
  destination_id text references public.destinations (id),
  title text not null check (char_length(title) between 3 and 160),
  body text not null check (char_length(body) between 1 and 10000),
  status text not null default 'published' check (status in ('published', 'pending', 'hidden', 'removed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.community_comments (
  id uuid primary key default gen_random_uuid(),
  post_id uuid not null references public.community_posts (id) on delete cascade,
  author_id uuid not null references auth.users (id) on delete cascade,
  body text not null check (char_length(body) between 1 and 5000),
  status text not null default 'published' check (status in ('published', 'pending', 'hidden', 'removed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.community_votes (
  user_id uuid not null references auth.users (id) on delete cascade,
  target_type text not null check (target_type in ('post', 'comment')),
  target_id uuid not null,
  value smallint not null check (value in (-1, 1)),
  created_at timestamptz not null default now(),
  primary key (user_id, target_type, target_id)
);

create table public.community_media (
  id uuid primary key default gen_random_uuid(),
  post_id uuid references public.community_posts (id) on delete cascade,
  author_id uuid not null references auth.users (id) on delete cascade,
  storage_path text not null,
  status text not null default 'pending' check (status in ('pending', 'published', 'removed')),
  created_at timestamptz not null default now()
);

create table public.community_reports (
  id uuid primary key default gen_random_uuid(),
  reporter_id uuid references auth.users (id) on delete set null,
  target_type text not null check (target_type in ('post', 'comment', 'user', 'media')),
  target_id uuid not null,
  reason text not null check (reason in ('spam', 'harassment', 'hate', 'scam', 'misinformation', 'private_info', 'sexual', 'violence', 'other')),
  details text check (char_length(details) <= 2000),
  status text not null default 'open' check (status in ('open', 'reviewing', 'actioned', 'dismissed')),
  created_at timestamptz not null default now()
);

create table public.user_blocks (
  blocker_id uuid not null references auth.users (id) on delete cascade,
  blocked_id uuid not null references auth.users (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (blocker_id, blocked_id),
  check (blocker_id <> blocked_id)
);

create table public.content_flags (
  id uuid primary key default gen_random_uuid(),
  target_type text not null,
  target_id uuid not null,
  source text not null check (source in ('keyword', 'ai', 'rate', 'report_threshold')),
  reason text not null,
  score numeric,
  created_at timestamptz not null default now()
);

create table public.moderation_actions (
  id uuid primary key default gen_random_uuid(),
  moderator_id uuid references auth.users (id) on delete set null,
  target_type text not null,
  target_id uuid not null,
  action text not null check (action in ('hide', 'remove', 'restore', 'warn', 'suspend', 'unsuspend', 'dismiss_report')),
  reason text,
  created_at timestamptz not null default now()
);

create table public.appeals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  moderation_action_id uuid references public.moderation_actions (id) on delete set null,
  body text not null check (char_length(body) <= 2000),
  status text not null default 'open' check (status in ('open', 'upheld', 'overturned')),
  created_at timestamptz not null default now()
);

create table public.badges (
  id text primary key,
  name jsonb not null,
  description jsonb
);

create table public.user_badges (
  user_id uuid not null references auth.users (id) on delete cascade,
  badge_id text not null references public.badges (id) on delete cascade,
  awarded_at timestamptz not null default now(),
  primary key (user_id, badge_id)
);

-- Authors cannot change moderation state; only admins / the service role can.
create or replace function public.protect_moderation_status()
returns trigger language plpgsql as $$
begin
  if public.is_service_role() or public.is_admin() then
    return new;
  end if;
  if tg_op = 'INSERT' then
    new.status := 'published';
  elsif new.status is distinct from old.status then
    new.status := old.status;
  end if;
  return new;
end;
$$;

create trigger community_posts_status before insert or update on public.community_posts
  for each row execute function public.protect_moderation_status();
create trigger community_comments_status before insert or update on public.community_comments
  for each row execute function public.protect_moderation_status();

-- ---------------------------------------------------------------- AI
create table public.ai_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users (id) on delete cascade,
  anonymous_id text,
  trip_id uuid references public.trips (id) on delete set null,
  created_at timestamptz not null default now()
);

create table public.ai_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.ai_sessions (id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  created_at timestamptz not null default now()
);

create table public.ai_tool_calls (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.ai_sessions (id) on delete cascade,
  message_id uuid references public.ai_messages (id) on delete set null,
  tool text not null,
  args jsonb not null default '{}'::jsonb,
  access text not null check (access in ('read', 'write', 'confirm')),
  decision text not null check (decision in ('execute', 'needs_confirmation', 'rejected')),
  result_summary text,
  created_at timestamptz not null default now()
);

create table public.ai_feedback (
  id uuid primary key default gen_random_uuid(),
  message_id uuid not null references public.ai_messages (id) on delete cascade,
  user_id uuid references auth.users (id) on delete cascade,
  helpful boolean not null,
  reason text,
  created_at timestamptz not null default now()
);

create table public.ai_usage (
  day date not null,
  provider text not null,
  model text not null,
  requests integer not null default 0,
  errors integer not null default 0,
  input_tokens bigint not null default 0,
  output_tokens bigint not null default 0,
  estimated_cost_usd numeric(12, 6) not null default 0,
  primary key (day, provider, model)
);

create table public.ai_evaluations (
  id uuid primary key default gen_random_uuid(),
  run_at timestamptz not null default now(),
  suite text not null,
  git_commit text,
  scores jsonb not null
);

-- ---------------------------------------------------------------- notifications + analytics
create table public.push_tokens (
  token text primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  platform text not null check (platform in ('ios', 'android', 'web')),
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);

create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  kind text not null,
  title text not null,
  body text,
  data jsonb not null default '{}'::jsonb,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.analytics_events (
  id bigint generated always as identity primary key,
  name text not null check (name ~ '^[a-z_]{3,48}$'),
  anonymous_id text not null check (char_length(anonymous_id) between 8 and 64),
  user_id uuid references auth.users (id) on delete set null,
  occurred_at timestamptz not null,
  received_at timestamptz not null default now(),
  platform text not null check (platform in ('ios', 'android', 'web')),
  app_version text,
  language text,
  trip_stage text,
  destination text,
  listing_id text,
  affiliate_partner text,
  attribution jsonb,
  properties jsonb not null default '{}'::jsonb check (pg_column_size(properties) < 4096)
);
create index analytics_events_name_time on public.analytics_events (name, occurred_at desc);

-- ---------------------------------------------------------------- verified travel data
create table public.emergency_contacts (
  id text primary key,
  country text not null default 'MA',
  city text,
  service text not null,
  label text not null,
  number text not null check (number ~ '^[0-9+ ]{2,20}$'),
  scope text,
  source text not null,
  last_verified date
);

create table public.travel_facts (
  id uuid primary key default gen_random_uuid(),
  topic text not null,
  destination_id text references public.destinations (id),
  content text not null,
  source text not null,
  last_verified date,
  valid_until date
);

-- Estimates, never official tariffs (Master Plan §16, §32).
create table public.price_guides (
  id uuid primary key default gen_random_uuid(),
  destination_id text references public.destinations (id),
  item text not null,
  vehicle_type text,
  min_minor integer not null check (min_minor >= 0),
  max_minor integer not null check (max_minor >= min_minor),
  currency text not null default 'MAD',
  unit text,
  source text not null,
  last_verified date,
  notes text
);

-- ---------------------------------------------------------------- audit
create table public.audit_log (
  id bigint generated always as identity primary key,
  actor_id uuid,
  action text not null,
  target_type text,
  target_id text,
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------- updated_at
create trigger touch_profiles before update on public.profiles for each row execute function public.touch_updated_at();
create trigger touch_user_preferences before update on public.user_preferences for each row execute function public.touch_updated_at();
create trigger touch_providers before update on public.providers for each row execute function public.touch_updated_at();
create trigger touch_listings before update on public.listings for each row execute function public.touch_updated_at();
create trigger touch_trips before update on public.trips for each row execute function public.touch_updated_at();
create trigger touch_bookings before update on public.bookings for each row execute function public.touch_updated_at();
create trigger touch_posts before update on public.community_posts for each row execute function public.touch_updated_at();
create trigger touch_comments before update on public.community_comments for each row execute function public.touch_updated_at();
