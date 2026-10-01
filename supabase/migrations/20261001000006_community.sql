-- Community v0.3 (Master Plan §28–29): feed view, automatic screening,
-- report threshold, and the admin moderation functions. AI is never the only
-- moderation layer: these rules run in the database for every write.

-- Note: moderation status changes made inside SECURITY DEFINER functions
-- (the report threshold, moderate()) pass protect_moderation_status, because
-- is_service_role() is true for the function owner.

-- 1. Feed: posts the caller may see (RLS applies: security_invoker), with the
-- author's display name, vote score and published comment count.
create or replace view public.community_feed with (security_invoker = true) as
select
  p.id, p.kind, p.destination_id, p.title, p.body, p.status, p.author_id, p.created_at,
  pr.display_name as author_name,
  coalesce((select sum(v.value) from public.community_votes v
            where v.target_type = 'post' and v.target_id = p.id), 0)::int as score,
  (select count(*) from public.community_comments c
   where c.post_id = p.id and c.status = 'published')::int as comment_count
from public.community_posts p
left join public.profiles pr on pr.id = p.author_id;
grant select on public.community_feed to anon, authenticated;

-- 2. Screening on write: link spam, scam keywords and posting rate. Flagged
-- content is held as 'pending' (visible to its author only) for review.
create or replace function public.screen_community_content()
returns trigger language plpgsql security definer set search_path = public as $$
declare
  item text := case tg_table_name when 'community_posts' then 'post' else 'comment' end;
  content text;
  links int;
  recent int;
  why text;
begin
  -- Screen only API callers. is_service_role() cannot be used here: inside this
  -- SECURITY DEFINER function current_user is always the owner.
  if coalesce(nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role', '') not in ('anon', 'authenticated')
     or public.is_admin() then
    return new;
  end if;
  content := coalesce(to_jsonb(new) ->> 'title' || E'\n', '') || new.body;
  select count(*) into links from regexp_matches(content, '(https?://|www\.)', 'gi');
  if links > 2 then
    why := 'link_spam';
  elsif content ~* '(wa\.me/|t\.me/|bitcoin|crypto ?(invest|trading)|western union|moneygram|casino|escort|guaranteed (profit|visa))' then
    why := 'scam_keyword';
  end if;
  if why is null and tg_op = 'INSERT' then
    if item = 'post' then
      select count(*) into recent from public.community_posts
      where author_id = new.author_id and created_at > now() - interval '10 minutes';
      if recent >= 5 then why := 'rate'; end if;
    else
      select count(*) into recent from public.community_comments
      where author_id = new.author_id and created_at > now() - interval '10 minutes';
      if recent >= 20 then why := 'rate'; end if;
    end if;
  end if;
  if why is not null then
    new.status := 'pending';
    insert into public.content_flags (target_type, target_id, source, reason)
    values (item, new.id, case when why = 'rate' then 'rate' else 'keyword' end, why);
  end if;
  return new;
end;
$$;

-- Trigger names sort after *_status so screening runs last.
create trigger community_posts_zscreen before insert or update of title, body on public.community_posts
  for each row execute function public.screen_community_content();
create trigger community_comments_zscreen before insert or update of body on public.community_comments
  for each row execute function public.screen_community_content();

-- 3. Reports: one per person and target; three different reporters hide the
-- content until a moderator reviews it.
create unique index if not exists community_reports_once
  on public.community_reports (reporter_id, target_type, target_id) where reporter_id is not null;

create or replace function public.apply_report_threshold()
returns trigger language plpgsql security definer set search_path = public as $$
declare
  reporters int;
begin
  if new.target_type not in ('post', 'comment') then
    return new;
  end if;
  select count(distinct reporter_id) into reporters from public.community_reports
  where target_type = new.target_type and target_id = new.target_id and status in ('open', 'reviewing');
  if reporters >= 3 then
    if new.target_type = 'post' then
      update public.community_posts set status = 'hidden' where id = new.target_id and status = 'published';
    else
      update public.community_comments set status = 'hidden' where id = new.target_id and status = 'published';
    end if;
    if found then
      insert into public.content_flags (target_type, target_id, source, reason, score)
      values (new.target_type, new.target_id, 'report_threshold', 'reports', reporters);
    end if;
  end if;
  return new;
end;
$$;

create trigger community_reports_threshold after insert on public.community_reports
  for each row execute function public.apply_report_threshold();

-- 4. Moderation (admins only). Every action is recorded in moderation_actions
-- and audit_log, and resolves the open reports on its target.
create or replace function public.moderate(p_target_type text, p_target_id uuid, p_action text, p_reason text default null)
returns void language plpgsql security definer set search_path = public as $$
declare
  next_status text;
  author uuid;
begin
  -- App admins, or trusted database access (the SQL Editor, the service
  -- role): callers without an anon/authenticated API role.
  if not (public.is_admin()
          or coalesce(nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role', '') not in ('anon', 'authenticated')) then
    raise exception 'admins only' using errcode = '42501';
  end if;
  if p_action in ('hide', 'remove', 'restore') then
    next_status := case p_action when 'hide' then 'hidden' when 'remove' then 'removed' else 'published' end;
    if p_target_type = 'post' then
      update public.community_posts set status = next_status where id = p_target_id returning author_id into author;
    elsif p_target_type = 'comment' then
      update public.community_comments set status = next_status where id = p_target_id returning author_id into author;
    else
      raise exception 'cannot % a %', p_action, p_target_type using errcode = '22023';
    end if;
    if author is null then
      raise exception 'no such %', p_target_type using errcode = 'P0002';
    end if;
  elsif p_action = 'suspend' then
    if p_target_type <> 'user' then raise exception 'suspend needs a user' using errcode = '22023'; end if;
    insert into public.user_suspensions (user_id, reason, ends_at, created_by)
    values (p_target_id, coalesce(p_reason, 'community guidelines'), now() + interval '7 days', auth.uid());
  elsif p_action = 'unsuspend' then
    update public.user_suspensions set ends_at = now()
    where user_id = p_target_id and (ends_at is null or ends_at > now());
  elsif p_action not in ('warn', 'dismiss_report') then
    raise exception 'unknown action %', p_action using errcode = '22023';
  end if;

  update public.community_reports
  set status = case when p_action in ('restore', 'dismiss_report') then 'dismissed' else 'actioned' end
  where target_type = p_target_type and target_id = p_target_id and status in ('open', 'reviewing');

  insert into public.moderation_actions (moderator_id, target_type, target_id, action, reason)
  values (auth.uid(), p_target_type, p_target_id, p_action, p_reason);
  insert into public.audit_log (actor_id, action, target_type, target_id, data)
  values (auth.uid(), 'moderation.' || p_action, p_target_type, p_target_id::text, jsonb_build_object('reason', p_reason));
end;
$$;

-- The review queue: content with open reports, or held by screening.
create or replace function public.moderation_queue()
returns table (
  target_type text, target_id uuid, status text, title text, body text, author_id uuid,
  open_reports int, report_reasons text[], flag_reasons text[], last_activity timestamptz
)
language plpgsql stable security definer set search_path = public as $$
begin
  -- App admins, or trusted database access (the SQL Editor, the service
  -- role): callers without an anon/authenticated API role.
  if not (public.is_admin()
          or coalesce(nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role', '') not in ('anon', 'authenticated')) then
    raise exception 'admins only' using errcode = '42501';
  end if;
  return query
  with items as (
    select 'post'::text as t, p.id, p.status, p.title, p.body, p.author_id, p.created_at from public.community_posts p
    union all
    select 'comment', c.id, c.status, null, c.body, c.author_id, c.created_at from public.community_comments c
  )
  select i.t, i.id, i.status, i.title, i.body, i.author_id,
    (select count(*)::int from public.community_reports r
     where r.target_type = i.t and r.target_id = i.id and r.status in ('open', 'reviewing')),
    (select coalesce(array_agg(distinct r.reason), '{}') from public.community_reports r
     where r.target_type = i.t and r.target_id = i.id and r.status in ('open', 'reviewing')),
    (select coalesce(array_agg(distinct f.reason), '{}') from public.content_flags f
     where f.target_type = i.t and f.target_id = i.id),
    greatest(i.created_at, (select max(r.created_at) from public.community_reports r
                            where r.target_type = i.t and r.target_id = i.id))
  from items i
  where i.status = 'pending'
     or exists (select 1 from public.community_reports r
                where r.target_type = i.t and r.target_id = i.id and r.status in ('open', 'reviewing'))
  order by 10 desc
  limit 200;
end;
$$;

revoke all on function public.moderate(text, uuid, text, text), public.moderation_queue() from public, anon;
grant execute on function public.moderate(text, uuid, text, text), public.moderation_queue() to authenticated;
revoke all on function public.screen_community_content(), public.apply_report_threshold() from public, anon, authenticated;
