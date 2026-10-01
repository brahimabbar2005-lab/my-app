/**
 * Community model: pure types and checks shared by the screens and tests.
 * The limits mirror the community tables' check constraints.
 */
export const POST_KINDS = ['question', 'trip_report', 'post'] as const;
export type PostKind = (typeof POST_KINDS)[number];

// Must match the check constraint on community_reports.reason.
export const REPORT_REASONS = [
  'spam',
  'scam',
  'harassment',
  'hate',
  'misinformation',
  'private_info',
  'sexual',
  'violence',
  'other',
] as const;
export type ReportReason = (typeof REPORT_REASONS)[number];

export interface FeedPost {
  id: string;
  kind: PostKind;
  destination_id: string | null;
  title: string;
  body: string;
  status: 'published' | 'pending' | 'hidden' | 'removed';
  author_id: string;
  author_name: string | null;
  created_at: string;
  score: number;
  comment_count: number;
}

export interface Comment {
  id: string;
  post_id: string;
  author_id: string;
  body: string;
  status: FeedPost['status'];
  created_at: string;
  author_name: string | null;
}

export interface PostDraft {
  kind: PostKind;
  destination_id: string | null;
  title: string;
  body: string;
}

export type DraftProblem = 'title_short' | 'title_long' | 'body_empty' | 'body_long';

/** Same limits as the table's check constraints, checked before sending. */
export function validateDraft(draft: PostDraft): DraftProblem | null {
  const title = draft.title.trim();
  const body = draft.body.trim();
  if (title.length < 3) return 'title_short';
  if (title.length > 160) return 'title_long';
  if (body.length < 1) return 'body_empty';
  if (body.length > 10000) return 'body_long';
  return null;
}

/** Days/hours/minutes ago, for post headers. */
export function ageParts(iso: string, now = Date.now()): { unit: 'm' | 'h' | 'd'; value: number } {
  const minutes = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return { unit: 'm', value: minutes };
  if (minutes < 60 * 24) return { unit: 'h', value: Math.floor(minutes / 60) };
  return { unit: 'd', value: Math.floor(minutes / (60 * 24)) };
}
