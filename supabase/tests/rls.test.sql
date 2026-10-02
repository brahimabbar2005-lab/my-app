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
select pg_temp.expect((select tagline ->> 'ar' from public.destinations where id = 'fes') is not null, 'taglines are localised');
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

-- Trip sync (v0.2): A syncs a device-built trip; B cannot overwrite it ----
begin;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-00000000000a","role":"authenticated"}', true);
select public.sync_trip(
  '{"id":"50000000-0000-4000-8000-00000000000a","user_id":"00000000-0000-0000-0000-00000000000a","title":"Synced","travelers_adults":2,"travelers_children":0}'::jsonb,
  '[{"id":"51000000-0000-4000-8000-000000000001","day_number":1},{"id":"51000000-0000-4000-8000-000000000002","day_number":2}]'::jsonb,
  '[{"id":"52000000-0000-4000-8000-000000000001","trip_day_id":"51000000-0000-4000-8000-000000000001","item_type":"destination","ref_id":"fes","title":"Fes","position":0},
    {"id":"52000000-0000-4000-8000-000000000002","trip_day_id":"","item_type":"article","ref_id":"wp-1","title":"Idea","position":0}]'::jsonb);
select pg_temp.expect((select count(*) from public.trip_items where trip_id = '50000000-0000-4000-8000-00000000000a') = 2, 'sync_trip stores items');
-- A second sync replaces rather than duplicates.
select public.sync_trip(
  '{"id":"50000000-0000-4000-8000-00000000000a","user_id":"00000000-0000-0000-0000-00000000000a","title":"Synced v2"}'::jsonb,
  '[{"id":"51000000-0000-4000-8000-000000000001","day_number":1}]'::jsonb,
  '[{"id":"52000000-0000-4000-8000-000000000001","trip_day_id":"51000000-0000-4000-8000-000000000001","item_type":"destination","ref_id":"fes","title":"Fes","position":0}]'::jsonb);
select pg_temp.expect((select count(*) from public.trip_items where trip_id = '50000000-0000-4000-8000-00000000000a') = 1, 'sync_trip replaces items');
select pg_temp.expect((select title from public.trips where id = '50000000-0000-4000-8000-00000000000a') = 'Synced v2', 'sync_trip updates the trip');
do $$ begin
  begin
    perform public.sync_trip('{"id":"50000000-0000-4000-8000-00000000000b","user_id":"00000000-0000-0000-0000-00000000000b"}'::jsonb, '[]', '[]');
    raise exception 'FAIL: A synced a trip owned by B';
  exception when insufficient_privilege then null; end;
end $$;
commit;

begin;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-00000000000b","role":"authenticated"}', true);
do $$ begin
  begin
    perform public.sync_trip('{"id":"50000000-0000-4000-8000-00000000000a","user_id":"00000000-0000-0000-0000-00000000000b","title":"hijack"}'::jsonb, '[]', '[]');
    raise exception 'FAIL: B overwrote A''s synced trip';
  exception when insufficient_privilege or unique_violation then null; end;
end $$;
commit;
select pg_temp.expect((select title from public.trips where id = '50000000-0000-4000-8000-00000000000a') = 'Synced v2', 'B could not change A''s synced trip');
select pg_temp.expect((select count(*) from public.trip_items where trip_id = '50000000-0000-4000-8000-00000000000a') = 1, 'B could not delete A''s synced items');

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

-- Community moderation (v0.3) ---------------------------------------------------
-- D writes, E/F/H report, M moderates.
insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-00000000000d', 'd@example.com'),
  ('00000000-0000-0000-0000-00000000000e', 'e@example.com'),
  ('00000000-0000-0000-0000-00000000000f', 'f@example.com'),
  ('00000000-0000-0000-0000-000000000011', 'h@example.com'),
  ('00000000-0000-0000-0000-000000000099', 'm@example.com');
insert into public.admin_users (user_id) values ('00000000-0000-0000-0000-000000000099');

begin;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-00000000000d","role":"authenticated"}', true);
insert into public.community_posts (id, author_id, kind, destination_id, title, body)
  values ('50000000-0000-0000-0000-00000000000d', auth.uid(), 'question', 'rabat', 'Rabat in winter?', 'Is Rabat worth a day in January?');
insert into public.community_posts (id, author_id, title, body)
  values ('50000000-0000-0000-0000-0000000000d2', auth.uid(), 'Cheap riads', 'Message me on wa.me/212600000000 for deals');
select pg_temp.expect((select status from public.community_posts where id = '50000000-0000-0000-0000-00000000000d') = 'published', 'normal posts publish');
select pg_temp.expect((select status from public.community_posts where id = '50000000-0000-0000-0000-0000000000d2') = 'pending', 'scam keywords hold a post as pending');
select pg_temp.expect((select count(*) from public.community_feed where id = '50000000-0000-0000-0000-0000000000d2') = 1, 'authors see their own pending post');
do $$ begin
  begin perform 1 from public.content_flags limit 1; raise exception 'FAIL: user read content_flags';
  exception when insufficient_privilege then null; end;
end $$;
do $$ begin
  begin perform public.moderation_queue(); raise exception 'FAIL: non-admin read the moderation queue';
  exception when insufficient_privilege then null; end;
end $$;
commit;
select pg_temp.expect(exists (select 1 from public.content_flags where target_id = '50000000-0000-0000-0000-0000000000d2' and reason = 'scam_keyword'), 'screening records a flag');

begin;
set local role anon;
select set_config('request.jwt.claims', '{"role":"anon"}', true);
select pg_temp.expect((select count(*) from public.community_feed where author_id = '00000000-0000-0000-0000-00000000000d') = 1, 'guests see only published posts in the feed');
commit;

-- Rate limit: the 6th post within ten minutes is held.
begin;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-000000000011","role":"authenticated"}', true);
insert into public.community_posts (author_id, title, body) select auth.uid(), 'Post ' || n, 'Body ' || n from generate_series(1, 6) n;
select pg_temp.expect((select count(*) from public.community_posts where author_id = auth.uid() and status = 'pending') = 1, 'posting faster than the rate limit is held');
commit;

-- Three different reporters hide a post; the same person cannot report twice.
do $$
declare reporter uuid;
begin
  foreach reporter in array array['00000000-0000-0000-0000-00000000000e', '00000000-0000-0000-0000-00000000000f', '00000000-0000-0000-0000-000000000011']::uuid[] loop
    perform set_config('request.jwt.claims', json_build_object('sub', reporter, 'role', 'authenticated')::text, true);
    set local role authenticated;
    insert into public.community_reports (reporter_id, target_type, target_id, reason)
      values (reporter, 'post', '50000000-0000-0000-0000-00000000000d', 'misinformation');
    reset role;
  end loop;
end $$;
select pg_temp.expect((select status from public.community_posts where id = '50000000-0000-0000-0000-00000000000d') = 'hidden', 'three reports hide a post');
select pg_temp.expect(exists (select 1 from public.content_flags where target_id = '50000000-0000-0000-0000-00000000000d' and source = 'report_threshold'), 'the threshold is recorded as a flag');

begin;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-00000000000e","role":"authenticated"}', true);
do $$ begin
  begin
    insert into public.community_reports (reporter_id, target_type, target_id, reason)
      values (auth.uid(), 'post', '50000000-0000-0000-0000-00000000000d', 'spam');
    raise exception 'FAIL: duplicate report accepted';
  exception when unique_violation then null; end;
end $$;
select pg_temp.expect((select count(*) from public.community_feed where id = '50000000-0000-0000-0000-00000000000d') = 0, 'hidden posts leave the feed');
commit;

begin;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-00000000000d","role":"authenticated"}', true);
update public.community_posts set status = 'published' where id = '50000000-0000-0000-0000-00000000000d';
select pg_temp.expect((select status from public.community_posts where id = '50000000-0000-0000-0000-00000000000d') = 'hidden', 'authors cannot un-hide');
do $$ begin
  begin perform public.moderate('post', '50000000-0000-0000-0000-00000000000d', 'restore'); raise exception 'FAIL: non-admin moderated';
  exception when insufficient_privilege then null; end;
end $$;
commit;

-- The moderator reviews the queue, restores the post and suspends D.
begin;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-000000000099","role":"authenticated"}', true);
select pg_temp.expect((select count(*) from public.moderation_queue() where target_id in
  ('50000000-0000-0000-0000-00000000000d', '50000000-0000-0000-0000-0000000000d2')) = 2, 'queue lists reported and held posts');
select pg_temp.expect((select open_reports from public.moderation_queue() where target_id = '50000000-0000-0000-0000-00000000000d') = 3, 'queue counts open reports');
select public.moderate('post', '50000000-0000-0000-0000-00000000000d', 'restore', 'accurate question');
select public.moderate('post', '50000000-0000-0000-0000-0000000000d2', 'remove', 'scam');
select public.moderate('user', '00000000-0000-0000-0000-00000000000d', 'suspend', 'scam links');
commit;
select pg_temp.expect((select status from public.community_posts where id = '50000000-0000-0000-0000-00000000000d') = 'published', 'restore republishes');
select pg_temp.expect((select status from public.community_posts where id = '50000000-0000-0000-0000-0000000000d2') = 'removed', 'remove removes');
select pg_temp.expect(not exists (select 1 from public.community_reports where target_id = '50000000-0000-0000-0000-00000000000d' and status = 'open'), 'restore resolves the reports');
select pg_temp.expect((select count(*) from public.moderation_queue()) >= 0, 'the SQL Editor (database owner) can read the queue');
select pg_temp.expect((select count(*) from public.moderation_actions where moderator_id = '00000000-0000-0000-0000-000000000099') = 3, 'every action is recorded');
select pg_temp.expect((select count(*) from public.audit_log where action like 'moderation.%') = 3, 'every action is audited');

begin;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-00000000000d","role":"authenticated"}', true);
do $$ begin
  begin
    insert into public.community_comments (post_id, author_id, body) values ('50000000-0000-0000-0000-00000000000d', auth.uid(), 'still here');
    raise exception 'FAIL: suspended user commented';
  exception when insufficient_privilege then null; end;
end $$;
commit;

begin;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-00000000000e","role":"authenticated"}', true);
insert into public.community_votes (user_id, target_type, target_id, value) values (auth.uid(), 'post', '50000000-0000-0000-0000-00000000000d', 1);
insert into public.community_comments (post_id, author_id, body) values ('50000000-0000-0000-0000-00000000000d', auth.uid(), 'Yes, the Kasbah of the Udayas is lovely.');
select pg_temp.expect((select score from public.community_feed where id = '50000000-0000-0000-0000-00000000000d') = 1, 'feed shows the vote score');
select pg_temp.expect((select comment_count from public.community_feed where id = '50000000-0000-0000-0000-00000000000d') = 1, 'feed counts comments');
commit;

-- Admin catalogue (v0.4) ---------------------------------------------------------
begin;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-00000000000e","role":"authenticated"}', true);
do $$ begin
  begin perform public.admin_save_listing('{"title":"Fake riad","category":"stay"}'); raise exception 'FAIL: non-admin saved a listing';
  exception when insufficient_privilege then null; end;
end $$;
do $$ begin
  begin perform public.admin_listings(); raise exception 'FAIL: non-admin listed admin listings';
  exception when insufficient_privilege then null; end;
end $$;
commit;

begin;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-000000000099","role":"authenticated"}', true);
create temp table saved_ids (name text, id text) on commit drop;
insert into saved_ids select 'riad', public.admin_save_listing(jsonb_build_object(
  'title', 'Riad Dar Test', 'category', 'stay', 'subtype', 'riad', 'destination_id', 'fes', 'status', 'published',
  'price_from_minor', 90000, 'image_url', 'https://comemorocco.com/x.jpg',
  'link_url', 'https://www.booking.com/hotel/ma/dar-test.html', 'link_is_partner', true, 'partner_name', 'Booking.com'));
insert into saved_ids select 'hostel', public.admin_save_listing(jsonb_build_object(
  'title', 'Draft hostel', 'category', 'stay', 'subtype', 'hostel', 'link_url', 'https://hostel.example/book'));
do $$ begin
  begin perform public.admin_save_listing('{"title":"Bad link","category":"stay","link_url":"http://insecure.example"}');
    raise exception 'FAIL: accepted a non-https link';
  exception when invalid_parameter_value then null; end;
end $$;
select pg_temp.expect((select count(*) from public.admin_listings() where id in (select id from saved_ids)) = 2, 'admin sees drafts too');
select pg_temp.expect((select partner_url from public.admin_listings() where id = (select id from saved_ids where name = 'riad'))
  = 'https://www.booking.com/hotel/ma/dar-test.html', 'partner link stored privately');
select pg_temp.expect((select website_url from public.listings where id = (select id from saved_ids where name = 'hostel'))
  = 'https://hostel.example/book', 'direct link is public');
-- Switching the riad to a direct link removes its partner link.
select public.admin_save_listing(jsonb_build_object('id', (select id from saved_ids where name = 'riad'), 'title', 'Riad Dar Test',
  'category', 'stay', 'subtype', 'riad', 'status', 'published', 'link_url', 'https://riad.example', 'link_is_partner', false));
select pg_temp.expect((select partner_url from public.admin_listings() where id = (select id from saved_ids where name = 'riad')) is null,
  'switching to a direct link drops the partner link');
do $$ begin
  begin perform 1 from public.affiliate_links limit 1; raise exception 'FAIL: app users read affiliate_links';
  exception when insufficient_privilege then null; end;
end $$;
commit;

begin;
set local role anon;
select set_config('request.jwt.claims', '{"role":"anon"}', true);
select pg_temp.expect(exists (select 1 from public.listings where title = 'Riad Dar Test' and subtype = 'riad' and status = 'published'),
  'guests see published stays');
select pg_temp.expect(not exists (select 1 from public.listings where title = 'Draft hostel'), 'guests do not see drafts');
commit;
select pg_temp.expect((select count(*) from public.audit_log where action = 'catalog.save_listing') = 3, 'catalogue saves are audited');

-- Every public table has RLS forced on.
select pg_temp.expect(not exists (
  select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind = 'r' and not (c.relrowsecurity and c.relforcerowsecurity)
), 'RLS enabled and forced on every public table');

\echo 'RLS tests passed'
