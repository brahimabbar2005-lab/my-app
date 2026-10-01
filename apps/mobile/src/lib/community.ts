/**
 * Community data (Master Plan §28–29). Reads go through the `community_feed`
 * view and RLS, so blocked authors and hidden content never reach the app;
 * writes are screened in the database (spam, scam keywords, posting rate) and
 * three reports hide content until a moderator reviews it.
 */
import {
  type Comment,
  type FeedPost,
  type PostDraft,
  type PostKind,
  type ReportReason,
  validateDraft,
} from './community-model';
import { supabase } from './supabase';

export * from './community-model';

type Result<T> = { data: T; error?: undefined } | { data?: undefined; error: string };

function client() {
  if (!supabase) throw new Error('not_configured');
  return supabase;
}

const FEED_COLUMNS = 'id,kind,destination_id,title,body,status,author_id,author_name,created_at,score,comment_count';

export async function fetchFeed(filter: { kind?: PostKind | null; destination?: string | null; viewer?: string | null }): Promise<Result<FeedPost[]>> {
  try {
    let query = client().from('community_feed').select(FEED_COLUMNS).order('created_at', { ascending: false }).limit(50);
    // Others' published posts, plus the viewer's own in any state (so a held
    // post does not silently vanish for its author).
    query = filter.viewer
      ? query.or(`status.eq.published,author_id.eq.${filter.viewer}`)
      : query.eq('status', 'published');
    if (filter.kind) query = query.eq('kind', filter.kind);
    if (filter.destination) query = query.eq('destination_id', filter.destination);
    const { data, error } = await query;
    return error ? { error: error.message } : { data: (data ?? []) as FeedPost[] };
  } catch (e) {
    return { error: String((e as Error).message) };
  }
}

export async function fetchPost(id: string): Promise<Result<{ post: FeedPost; comments: Comment[]; myVote: number }>> {
  try {
    const db = client();
    const [post, comments, session] = await Promise.all([
      db.from('community_feed').select(FEED_COLUMNS).eq('id', id).maybeSingle(),
      db
        .from('community_comments')
        .select('id,post_id,author_id,body,status,created_at')
        .eq('post_id', id)
        .order('created_at', { ascending: true }),
      db.auth.getSession(),
    ]);
    if (post.error) return { error: post.error.message };
    if (!post.data) return { error: 'not_found' };
    const uid = session.data.session?.user.id;
    let myVote = 0;
    if (uid) {
      const { data } = await db
        .from('community_votes')
        .select('value')
        .eq('user_id', uid)
        .eq('target_type', 'post')
        .eq('target_id', id)
        .maybeSingle();
      myVote = data?.value ?? 0;
    }
    // Comments reference auth.users, so author names are a second lookup.
    const rows = ((comments.data ?? []) as Omit<Comment, 'author_name'>[]).filter(
      (c) => c.status === 'published' || c.author_id === uid,
    );
    const authorIds = [...new Set(rows.map((c) => c.author_id))];
    const names = new Map<string, string | null>();
    if (authorIds.length) {
      const { data } = await db.from('profiles').select('id,display_name').in('id', authorIds);
      for (const p of (data ?? []) as { id: string; display_name: string | null }[]) names.set(p.id, p.display_name);
    }
    return {
      data: {
        post: post.data as FeedPost,
        comments: rows.map((c) => ({ ...c, author_name: names.get(c.author_id) ?? null })),
        myVote,
      },
    };
  } catch (e) {
    return { error: String((e as Error).message) };
  }
}

export async function createPost(userId: string, draft: PostDraft): Promise<Result<{ id: string; status: FeedPost['status'] }>> {
  const problem = validateDraft(draft);
  if (problem) return { error: problem };
  const { data, error } = await client()
    .from('community_posts')
    .insert({
      author_id: userId,
      kind: draft.kind,
      destination_id: draft.destination_id,
      title: draft.title.trim(),
      body: draft.body.trim(),
    })
    .select('id,status')
    .single();
  return error ? { error: error.message } : { data: data as { id: string; status: FeedPost['status'] } };
}

export async function addComment(userId: string, postId: string, body: string): Promise<Result<Comment['status']>> {
  const text = body.trim();
  if (!text || text.length > 5000) return { error: 'body_empty' };
  const { data, error } = await client()
    .from('community_comments')
    .insert({ post_id: postId, author_id: userId, body: text })
    .select('status')
    .single();
  return error ? { error: error.message } : { data: (data as { status: Comment['status'] }).status };
}

/** value 0 removes the vote. */
export async function vote(userId: string, postId: string, value: -1 | 0 | 1): Promise<Result<true>> {
  const db = client();
  const target = { user_id: userId, target_type: 'post', target_id: postId };
  const { error } =
    value === 0
      ? await db.from('community_votes').delete().match(target)
      : await db.from('community_votes').upsert({ ...target, value });
  return error ? { error: error.message } : { data: true };
}

export async function report(
  userId: string,
  target: { type: 'post' | 'comment' | 'user'; id: string },
  reason: ReportReason,
  details?: string,
): Promise<Result<'filed' | 'already'>> {
  const { error } = await client()
    .from('community_reports')
    .insert({ reporter_id: userId, target_type: target.type, target_id: target.id, reason, details: details?.trim() || null });
  if (error?.code === '23505') return { data: 'already' };
  return error ? { error: error.message } : { data: 'filed' };
}

export async function blockUser(userId: string, blockedId: string): Promise<Result<true>> {
  const { error } = await client().from('user_blocks').upsert({ blocker_id: userId, blocked_id: blockedId });
  return error ? { error: error.message } : { data: true };
}

// ---------------------------------------------------------------- moderation
// Admin-only: the database refuses these for everyone else (42501).

export interface QueueItem {
  target_type: 'post' | 'comment';
  target_id: string;
  status: FeedPost['status'];
  title: string | null;
  body: string;
  author_id: string;
  open_reports: number;
  report_reasons: string[];
  flag_reasons: string[];
  last_activity: string;
}

export type ModerationAction = 'restore' | 'hide' | 'remove' | 'dismiss_report' | 'suspend' | 'unsuspend';

export async function isAdmin(): Promise<boolean> {
  if (!supabase) return false;
  const { data } = await supabase.rpc('is_admin');
  return data === true;
}

export async function fetchQueue(): Promise<Result<QueueItem[]>> {
  try {
    const { data, error } = await client().rpc('moderation_queue');
    return error ? { error: error.message } : { data: (data ?? []) as QueueItem[] };
  } catch (e) {
    return { error: String((e as Error).message) };
  }
}

export async function moderate(
  target: { type: 'post' | 'comment' | 'user'; id: string },
  action: ModerationAction,
  reason?: string,
): Promise<Result<true>> {
  const { error } = await client().rpc('moderate', {
    p_target_type: target.type,
    p_target_id: target.id,
    p_action: action,
    p_reason: reason?.trim() || null,
  });
  return error ? { error: error.message } : { data: true };
}
