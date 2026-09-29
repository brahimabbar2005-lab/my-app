-- RLS tests (Master Plan §44, §54). Run by scripts/test-supabase.sh after the
-- migrations and seeds. Every block either passes silently or raises
-- 'FAIL: …'. Users act through the same roles and JWT claims Supabase uses.

\set ON_ERROR_STOP on
set client_min_messages = warning;

-- Fixtures (as the owner) -----------------------------------------------
insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-00000000000a', 'a@example.com'),
  ('00000000-0000-0000-0000-00000000000b', 'b@example.com'),
  ('00000000-0000-0000-0000-00000000000c', 'c@example.com');
insert into public.user_suspensions (user_id, reason) values ('00000000-0000-0000-0000-00000000000c', 'test');
insert into public.listings (id, kind, category, title, status) values ('DRAFT-1', 'direct', 'stay', 'Hidden draft', 'draft');

create or replace function pg_temp.expect(ok boolean, message text) returns void language plpgsql as $$
begin
  if not ok then raise exception 'FAIL: %', message; end if;
end $$;

-- Profiles were created by the auth trigger.
select pg_temp.expect((select count(*) from public.profiles) = 3, 'handle_new_user creates profiles');
select pg_temp.expect((select count(*) from public.user_preferences) = 3, 'handle_new_user creates preferences');

-- Anonymous visitor -------------------------------------------------------
begin;
set local role anon;
select set_config('request.jwt.claims', '{"role":"anon"}', true);
select pg_temp.expect((select count(*) from public.destinations) >= 11, 'anon reads destinations');
select pg_temp.expect((select count(*) from public.listings where status = 'published') > 0, 'anon reads published listings');
select pg_temp.expect(not exists (select 1 from public.listings where id = 'DRAFT-1'), 'anon cannot see draft listings');
select pg_temp.expect((select count(*) from public.trips) = 0, 'anon sees no trips');
select pg_temp.expect((select count(*) from public.emergency_contacts) = 4, 'anon reads emergency contacts');
do $$ begin
  begin perform 1 from public.affiliate_links limit 1; raise exception 'FAIL: anon read affiliate_links';
  exception when insufficient_privilege then null; end;
end $$;
insert into public.analytics_events (name, anonymous_id, occurred_at, platform) values ('app_opened', 'anon-device-0001', now(), 'web');
do $$ begin
  begin perform 1 from public.analytics_events limit 1; raise exception 'FAIL: anon read analytics';
  exception when insufficient_privilege then null; end;
end $$;
commit;

-- User A ---------------------------------------------------------------------
begin;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-00000000000a","role":"authenticated"}', true);
insert into public.trips (id, user_id, title) values ('10000000-0000-0000-0000-00000000000a', '00000000-0000-0000-0000-00000000000a', 'A in Morocco');
insert into public.trip_days (trip_id, day_number) values ('10000000-0000-0000-0000-00000000000a', 1);
insert into public.trip_items (trip_id, item_type, ref_id, title) values ('10000000-0000-0000-0000-00000000000a', 'listing', 'GYG-008', 'Desert');
insert into public.saved_places (user_id, ref_type, ref_id) values ('00000000-0000-0000-0000-00000000000a', 'destination', 'fes');
insert into public.ai_sessions (id, user_id) values ('20000000-0000-0000-0000-00000000000a', '00000000-0000-0000-0000-00000000000a');
-- A tries to post as moderated/removed: the trigger forces 'published'.
insert into public.community_posts (id, author_id, title, body, status)
  values ('30000000-0000-0000-0000-00000000000a', '00000000-0000-0000-0000-00000000000a', 'Fes tips', 'Get lost in the medina.', 'removed');
select pg_temp.expect((select status from public.community_posts where id = '30000000-0000-0000-0000-00000000000a') = 'published',
  'authors cannot choose moderation status on insert');
update public.community_posts set status = 'hidden', body = 'Edited' where id = '30000000-0000-0000-0000-00000000000a';
update public.profiles set display_name = 'Amina' where id = auth.uid();
select pg_temp.expect((select display_name from public.profiles where id = auth.uid()) = 'Amina', 'users can edit their display name');
select pg_temp.expect((select status from public.community_posts where id = '30000000-0000-0000-0000-00000000000a') = 'published',
  'authors cannot change moderation status');
select pg_temp.expect((select body from public.community_posts where id = '30000000-0000-0000-0000-00000000000a') = 'Edited',
  'authors can edit their own text');
do $$ begin
  begin update public.profiles set status = 'suspended' where id = auth.uid(); raise exception 'FAIL: user changed own profile status';
  exception when insufficient_privilege then null; end;
end $$;
do $$ begin
  begin
    insert into public.analytics_events (name, anonymous_id, user_id, occurred_at, platform)
      values ('app_opened', 'device-a-000001', '00000000-0000-0000-0000-00000000000b', now(), 'ios');
    raise exception 'FAIL: A sent analytics as B';
  exception when insufficient_privilege then null; end;
end $$;
do $$ begin
  begin perform 1 from public.affiliate_clicks limit 1; raise exception 'FAIL: user read affiliate_clicks';
  exception when insufficient_privilege then null; end;
end $$;
do $$ begin
  begin
    insert into public.bookings (user_id, idempotency_key) values (auth.uid(), 'k1');
    raise exception 'FAIL: client created a booking directly';
  exception when insufficient_privilege then null; end;
end $$;
select pg_temp.expect((public.export_my_data() -> 'trips' -> 0 ->> 'title') = 'A in Morocco', 'export_my_data includes trips');
commit;

-- User B -----------------------------------------------------------------------
begin;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-00000000000b","role":"authenticated"}', true);
select pg_temp.expect((select count(*) from public.trips) = 0, 'B cannot see A''s trips');
select pg_temp.expect((select count(*) from public.trip_items) = 0, 'B cannot see A''s trip items');
select pg_temp.expect((select count(*) from public.saved_places) = 0, 'B cannot see A''s saved places');
select pg_temp.expect((select count(*) from public.ai_sessions) = 0, 'B cannot see A''s AI sessions');
update public.trips set title = 'hijacked' where id = '10000000-0000-0000-0000-00000000000a';
do $$ begin
  begin
    insert into public.trip_items (trip_id, item_type, title) values ('10000000-0000-0000-0000-00000000000a', 'note', 'x');
    raise exception 'FAIL: B wrote into A''s trip';
  exception when insufficient_privilege then null; end;
end $$;
do $$ begin
  begin
    insert into public.trips (user_id, title) values ('00000000-0000-0000-0000-00000000000a', 'planted');
    raise exception 'FAIL: B created a trip owned by A';
  exception when insufficient_privilege then null; end;
end $$;
update public.profiles set display_name = 'pwned' where id = '00000000-0000-0000-0000-00000000000a';
select pg_temp.expect((select count(*) from public.community_posts) = 1, 'B sees A''s published post');
insert into public.community_reports (reporter_id, target_type, target_id, reason)
  values (auth.uid(), 'post', '30000000-0000-0000-0000-00000000000a', 'spam');
insert into public.user_blocks (blocker_id, blocked_id) values (auth.uid(), '00000000-0000-0000-0000-00000000000a');
select pg_temp.expect((select count(*) from public.community_posts) = 0, 'blocked authors disappear for the blocker');
delete from public.community_posts where id = '30000000-0000-0000-0000-00000000000a';
commit;

select pg_temp.expect((select title from public.trips where id = '10000000-0000-0000-0000-00000000000a') = 'A in Morocco', 'B could not edit A''s trip');
select pg_temp.expect((select display_name from public.profiles where id = '00000000-0000-0000-0000-00000000000a') = 'Amina', 'B could not edit A''s profile');
select pg_temp.expect(exists (select 1 from public.community_posts where id = '30000000-0000-0000-0000-00000000000a'), 'B could not delete A''s post');

-- Suspended user C ---------------------------------------------------------
begin;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-00000000000c","role":"authenticated"}', true);
do $$ begin
  begin
    insert into public.community_posts (author_id, title, body) values (auth.uid(), 'Spam', 'spam spam');
    raise exception 'FAIL: suspended user posted';
  exception when insufficient_privilege then null; end;
end $$;
commit;

-- Account deletion (A) --------------------------------------------------------
insert into public.affiliate_clicks (id, listing_id, partner, user_id)
  values ('40000000-0000-0000-0000-00000000000a', 'GYG-008', 'getyourguide', '00000000-0000-0000-0000-00000000000a');
begin;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-00000000000a","role":"authenticated"}', true);
select public.delete_my_account();
commit;
select pg_temp.expect(not exists (select 1 from auth.users where id = '00000000-0000-0000-0000-00000000000a'), 'account removed');
select pg_temp.expect(not exists (select 1 from public.trips where user_id = '00000000-0000-0000-0000-00000000000a'), 'trips removed with account');
select pg_temp.expect(not exists (select 1 from public.community_posts where author_id = '00000000-0000-0000-0000-00000000000a'), 'posts removed with account');
select pg_temp.expect(not exists (select 1 from public.ai_sessions where user_id = '00000000-0000-0000-0000-00000000000a'), 'AI sessions removed with account');
select pg_temp.expect((select user_id from public.affiliate_clicks where id = '40000000-0000-0000-0000-00000000000a') is null, 'affiliate clicks de-identified');
select pg_temp.expect(exists (select 1 from public.audit_log where action = 'account_deleted' and actor_id is null), 'deletion audited without personal data');
select pg_temp.expect(exists (select 1 from public.community_reports where reason = 'spam'), 'reports filed by others survive');

-- Anonymous callers cannot delete anything.
begin;
set local role anon;
do $$ begin
  begin perform public.delete_my_account(); raise exception 'FAIL: anon called delete_my_account';
  exception when insufficient_privilege then null; end;
end $$;
commit;

-- Every public table has RLS forced on.
select pg_temp.expect(not exists (
  select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind = 'r' and not (c.relrowsecurity and c.relforcerowsecurity)
), 'RLS enabled and forced on every public table');

\echo 'RLS tests passed'
