# Milestone v0.3 — Community + moderation (Master Plan §28–29)

## What shipped
- **Community tab.** A feed of questions, trip reports and tips that can be filtered by type and destination. Guests can read; posting, replying, voting and reporting need an account.
- **Post screen.** Shows replies, a helpful / not-helpful vote, report (a required reason plus optional details) and block. Blocked travellers' posts and replies disappear for the person who blocked them, enforced by RLS.
- **Compose screen.** Type and destination pickers. The same length limits as the database are checked before sending. Held posts tell the author they're waiting for review.
- **Database rules** (`supabase/migrations/20261001000006_community.sql`). They run on every write, so they don't depend on the app or on AI:
  - **Screening:** more than 2 links, or scam keywords (for example `wa.me/` links, crypto investing, Western Union), hold a post or reply as `pending`. Posting faster than 5 posts or 20 replies in 10 minutes is held too. Each hold writes a `content_flags` row.
  - **Report threshold:** one report per person per item. 3 different reporters hide the item until a moderator reviews it.
  - **`moderation_queue()`** lists content with open reports or held by screening.
  - **`moderate(type, id, action, reason)`** handles hide / remove / restore / warn / suspend (7 days) / unsuspend / dismiss_report. Every action resolves the open reports and is written to `moderation_actions` and `audit_log`.
  - Both functions accept app admins (`admin_users`) and the Supabase SQL Editor. Everyone else gets `42501`.
- **Strings** in en/fr/es/ar, and the analytics events `community_comment_created`, `content_reported` and `user_blocked`.

## Verification
- RLS tests (`scripts/test-supabase.sh`), 20 new checks:
  - normal posts publish; scam links and posting too fast are held
  - authors see their own held posts; guests don't
  - users can't read flags or the queue
  - 3 reports hide a post, and duplicate reports are refused
  - authors can't un-hide their posts
  - non-admins can't moderate
  - the admin queue lists reported and held posts, and restore / remove / suspend work and are recorded and audited
  - suspended users can't reply
  - the feed shows vote scores and reply counts
- `supabase/setup/all-in-one.sql` rebuilt and re-verified on an empty Postgres 16 (setup plus all RLS tests).
- Unit tests: report reasons and post kinds match the database constraints; the draft limits; post age formatting.
- Browser (Playwright, simulated Supabase answers):
  - feed and filters
  - own posts labelled "You"
  - reply authors
  - vote, reply, report and block
  - compose: a held post shows the review notice and can't be sent twice
  - no console errors
  - Screenshots: `docs/screenshots/community-*.png`.

## To switch it on in the live project
1. Supabase → SQL Editor → New query → paste `supabase/migrations/20261001000006_community.sql` → Run.
2. To moderate from the app later, make yourself an admin (Authentication → Users → copy your user id):
   `insert into public.admin_users (user_id) values ('<your user id>');`
3. Until the admin screen exists, moderate in the SQL Editor:
   `select * from public.moderation_queue();` then
   `select public.moderate('post', '<id>', 'restore', 'ok');`

## Not in this milestone
- An admin moderation screen. The functions it will call exist and are tested.
- Photos in posts. `community_media` and its RLS exist; uploads need Storage rules and image moderation first.
- AI answers that cite community posts.
