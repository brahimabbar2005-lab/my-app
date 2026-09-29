-- Account self-service (Master Plan §14, §19, §56): delete account, delete
-- content, export data. Required before store submission (Apple 5.1.1(v),
-- Google Play account deletion policy).

-- Everything the platform holds about the caller, as one JSON document.
create or replace function public.export_my_data()
returns jsonb language plpgsql stable security definer set search_path = public as $$
declare uid uuid := auth.uid();
begin
  if uid is null then raise exception 'not signed in' using errcode = '42501'; end if;
  return jsonb_build_object(
    'exported_at', now(),
    'user_id', uid,
    'profile', (select to_jsonb(p) from profiles p where p.id = uid),
    'preferences', (select to_jsonb(p) from user_preferences p where p.user_id = uid),
    'trips', coalesce((select jsonb_agg(to_jsonb(t) || jsonb_build_object(
        'days', (select coalesce(jsonb_agg(to_jsonb(d)), '[]') from trip_days d where d.trip_id = t.id),
        'items', (select coalesce(jsonb_agg(to_jsonb(i)), '[]') from trip_items i where i.trip_id = t.id)))
      from trips t where t.user_id = uid), '[]'),
    'saved_places', coalesce((select jsonb_agg(to_jsonb(s)) from saved_places s where s.user_id = uid), '[]'),
    'bookings', coalesce((select jsonb_agg(to_jsonb(b)) from bookings b where b.user_id = uid), '[]'),
    'community_posts', coalesce((select jsonb_agg(to_jsonb(c)) from community_posts c where c.author_id = uid), '[]'),
    'community_comments', coalesce((select jsonb_agg(to_jsonb(c)) from community_comments c where c.author_id = uid), '[]'),
    'reports_filed', coalesce((select jsonb_agg(to_jsonb(r)) from community_reports r where r.reporter_id = uid), '[]'),
    'blocks', coalesce((select jsonb_agg(to_jsonb(b)) from user_blocks b where b.blocker_id = uid), '[]'),
    'ai_sessions', coalesce((select jsonb_agg(to_jsonb(s) || jsonb_build_object(
        'messages', (select coalesce(jsonb_agg(to_jsonb(m) order by m.created_at), '[]') from ai_messages m where m.session_id = s.id)))
      from ai_sessions s where s.user_id = uid), '[]'),
    'push_tokens', coalesce((select jsonb_agg(jsonb_build_object('platform', platform, 'created_at', created_at))
      from push_tokens where user_id = uid), '[]')
  );
end;
$$;

-- Removes the caller's community contributions but keeps the account.
create or replace function public.delete_my_content()
returns void language plpgsql security definer set search_path = public as $$
declare uid uuid := auth.uid();
begin
  if uid is null then raise exception 'not signed in' using errcode = '42501'; end if;
  delete from community_votes where user_id = uid;
  delete from community_media where author_id = uid;
  delete from community_comments where author_id = uid;
  delete from community_posts where author_id = uid;
  insert into audit_log (actor_id, action, target_type) values (uid, 'delete_my_content', 'user');
end;
$$;

-- Permanently deletes the caller's account. Personal rows cascade from
-- auth.users; rows kept for accounting or safety (affiliate clicks, filed
-- reports, analytics) are de-identified by ON DELETE SET NULL. The audit
-- entry keeps no personal data.
create or replace function public.delete_my_account()
returns void language plpgsql security definer set search_path = public, auth as $$
declare uid uuid := auth.uid();
begin
  if uid is null then raise exception 'not signed in' using errcode = '42501'; end if;
  perform public.delete_my_content();
  delete from auth.users where id = uid;
  insert into audit_log (actor_id, action, target_type) values (null, 'account_deleted', 'user');
end;
$$;

revoke all on function public.export_my_data(), public.delete_my_content(), public.delete_my_account() from public, anon;
grant execute on function public.export_my_data(), public.delete_my_content(), public.delete_my_account() to authenticated;
