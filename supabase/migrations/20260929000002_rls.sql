-- Row Level Security for every table (Master Plan §32, §44).
-- Frontend authorization is never trusted: these policies are the boundary.

-- 1. RLS on, everywhere.
do $$
declare t record;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t.tablename);
    execute format('alter table public.%I force row level security', t.tablename);
  end loop;
end $$;

-- 2. Privileges. Explicit, rather than relying on platform defaults.
grant usage on schema public to anon, authenticated, service_role;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant select on all tables in schema public to anon;
grant all on all tables in schema public to service_role;
grant usage, select on all sequences in schema public to authenticated, service_role;

-- Defence in depth: server-only tables are not even selectable by clients.
revoke all on public.affiliate_links, public.affiliate_clicks, public.affiliate_conversions,
  public.affiliate_commissions, public.ai_usage, public.ai_evaluations, public.audit_log,
  public.content_flags, public.admin_users
  from anon, authenticated;
revoke insert, update, delete on public.destinations, public.categories, public.places,
  public.listings, public.listing_images, public.listing_categories, public.listing_locations,
  public.content_items, public.badges, public.user_badges, public.emergency_contacts,
  public.travel_facts, public.price_guides, public.affiliate_programs, public.moderation_actions,
  public.user_suspensions, public.booking_status_history
  from authenticated;
grant insert on public.analytics_events to anon;

-- 3. Public catalogue: readable by everyone.
create policy "public read" on public.destinations for select using (true);
create policy "public read" on public.categories for select using (true);
create policy "public read" on public.places for select using (true);
create policy "public read" on public.content_items for select using (true);
create policy "public read" on public.badges for select using (true);
create policy "public read" on public.user_badges for select using (true);
create policy "public read" on public.emergency_contacts for select using (true);
create policy "public read" on public.travel_facts for select using (true);
create policy "public read" on public.price_guides for select using (true);
create policy "public read" on public.affiliate_programs for select using (true);

create policy "published listings" on public.listings for select
  using (status = 'published' or public.is_provider_member(provider_id) or public.is_admin());
create policy "listing images" on public.listing_images for select using (
  exists (select 1 from public.listings l where l.id = listing_id and (l.status = 'published' or public.is_provider_member(l.provider_id))));
create policy "listing categories" on public.listing_categories for select using (true);
create policy "listing locations" on public.listing_locations for select using (true);
create policy "availability read" on public.provider_availability for select using (true);
create policy "availability manage" on public.provider_availability for all
  using (exists (select 1 from public.listings l where l.id = listing_id and public.is_provider_member(l.provider_id)))
  with check (exists (select 1 from public.listings l where l.id = listing_id and public.is_provider_member(l.provider_id)));

-- 4. People.
create policy "profiles are public" on public.profiles for select using (true);
create policy "update own profile" on public.profiles for update
  using (id = auth.uid()) with check (id = auth.uid());
-- Profile status is moderation state, not user-editable. A column-level
-- REVOKE does not override a table-level GRANT, so update is re-granted per
-- editable column instead.
revoke update on public.profiles from authenticated;
grant update (display_name, avatar_url) on public.profiles to authenticated;

create policy "own preferences" on public.user_preferences for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy "own suspensions" on public.user_suspensions for select using (user_id = auth.uid() or public.is_admin());

-- 5. Trips and saved places: owner only.
create policy "own trips" on public.trips for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "own trip days" on public.trip_days for all using (public.owns_trip(trip_id)) with check (public.owns_trip(trip_id));
create policy "own trip items" on public.trip_items for all using (public.owns_trip(trip_id)) with check (public.owns_trip(trip_id));
create policy "own saved places" on public.saved_places for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- 6. Providers and bookings.
create policy "active providers are public" on public.providers for select
  using (status = 'active' or public.is_provider_member(id) or public.is_admin());
create policy "members update provider" on public.providers for update
  using (public.is_provider_member(id)) with check (public.is_provider_member(id));
revoke update on public.providers from authenticated;
grant update (name, kind) on public.providers to authenticated;
create policy "own membership" on public.provider_users for select using (user_id = auth.uid() or public.is_admin());
create policy "provider documents" on public.provider_documents for all
  using (public.is_provider_member(provider_id)) with check (public.is_provider_member(provider_id));

create policy "customer or provider reads booking" on public.bookings for select
  using (user_id = auth.uid() or public.is_provider_member(provider_id) or public.is_admin());
-- Bookings are created and moved between states by server functions (idempotent,
-- audited). No client insert/update policy exists yet.
create policy "booking items follow booking" on public.booking_items for select using (
  exists (select 1 from public.bookings b where b.id = booking_id
          and (b.user_id = auth.uid() or public.is_provider_member(b.provider_id) or public.is_admin())));
create policy "booking history follows booking" on public.booking_status_history for select using (
  exists (select 1 from public.bookings b where b.id = booking_id
          and (b.user_id = auth.uid() or public.is_provider_member(b.provider_id) or public.is_admin())));

-- 7. Community. Published content is public, minus users the viewer blocked;
-- authors see their own content in any state; suspended users cannot write.
create policy "read posts" on public.community_posts for select using (
  (status = 'published' and not exists (
     select 1 from public.user_blocks b where b.blocker_id = auth.uid() and b.blocked_id = author_id))
  or author_id = auth.uid() or public.is_admin());
create policy "write own posts" on public.community_posts for insert
  with check (author_id = auth.uid() and not public.is_suspended(auth.uid()));
create policy "edit own posts" on public.community_posts for update
  using (author_id = auth.uid() and not public.is_suspended(auth.uid()))
  with check (author_id = auth.uid());
create policy "delete own posts" on public.community_posts for delete using (author_id = auth.uid());

create policy "read comments" on public.community_comments for select using (
  (status = 'published' and not exists (
     select 1 from public.user_blocks b where b.blocker_id = auth.uid() and b.blocked_id = author_id))
  or author_id = auth.uid() or public.is_admin());
create policy "write own comments" on public.community_comments for insert
  with check (author_id = auth.uid() and not public.is_suspended(auth.uid()));
create policy "edit own comments" on public.community_comments for update
  using (author_id = auth.uid() and not public.is_suspended(auth.uid())) with check (author_id = auth.uid());
create policy "delete own comments" on public.community_comments for delete using (author_id = auth.uid());

create policy "read votes" on public.community_votes for select using (true);
create policy "own votes" on public.community_votes for insert with check (user_id = auth.uid() and not public.is_suspended(auth.uid()));
create policy "change own votes" on public.community_votes for update using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "remove own votes" on public.community_votes for delete using (user_id = auth.uid());

create policy "read published media" on public.community_media for select using (status = 'published' or author_id = auth.uid());
create policy "upload own media" on public.community_media for insert
  with check (author_id = auth.uid() and not public.is_suspended(auth.uid()));
create policy "delete own media" on public.community_media for delete using (author_id = auth.uid());
revoke update on public.community_media from authenticated;

create policy "file reports" on public.community_reports for insert with check (reporter_id = auth.uid());
create policy "see own reports" on public.community_reports for select using (reporter_id = auth.uid() or public.is_admin());
revoke update, delete on public.community_reports from authenticated;

create policy "own blocks" on public.user_blocks for all using (blocker_id = auth.uid()) with check (blocker_id = auth.uid());

create policy "admins read moderation" on public.moderation_actions for select using (public.is_admin());
create policy "own appeals" on public.appeals for select using (user_id = auth.uid() or public.is_admin());
create policy "file appeals" on public.appeals for insert with check (user_id = auth.uid());
revoke update, delete on public.appeals from authenticated;

-- 8. AI history: owner only. Guests' AI history lives in the AI service, not here.
create policy "own ai sessions" on public.ai_sessions for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "own ai messages" on public.ai_messages for select using (
  exists (select 1 from public.ai_sessions s where s.id = session_id and s.user_id = auth.uid()));
create policy "own ai tool calls" on public.ai_tool_calls for select using (
  exists (select 1 from public.ai_sessions s where s.id = session_id and s.user_id = auth.uid()));
revoke insert, update, delete on public.ai_messages, public.ai_tool_calls from authenticated;
create policy "own ai feedback" on public.ai_feedback for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- 9. Notifications.
create policy "own push tokens" on public.push_tokens for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "own notifications" on public.notifications for select using (user_id = auth.uid());
create policy "mark own notifications read" on public.notifications for update using (user_id = auth.uid()) with check (user_id = auth.uid());
revoke insert, delete on public.notifications from authenticated;

-- 10. Analytics: write-only for clients. A signed-in client may only attach its own id.
create policy "send events" on public.analytics_events for insert to anon, authenticated
  with check (user_id is null or user_id = auth.uid());
revoke select, update, delete on public.analytics_events from anon, authenticated;
