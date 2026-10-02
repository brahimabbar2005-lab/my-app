# ComeMorocco — project handoff (read this first in a new chat)

_Last updated: 2026-10-02 · branch `claude/gifted-franklin-puuz00` · repo `brahimabbar2005-lab/my-app` · latest commit at writing: `a783fd7`_

You are continuing the development of **ComeMorocco**, a mobile app (iOS + Android, Expo) for tourists and travellers coming to Morocco. The owner is Brahim (non-developer; explain steps simply, step by step, with screenshots of what to click when needed). Work on branch `claude/gifted-franklin-puuz00`, commit with clear messages, push, keep CI green. **Never commit secrets.**

---

## 1. The product (owner's vision)

- **What it is:** a travel app for Morocco combining the ideas of GetYourGuide (tours, activities), Booking (hotels, riads, hostels), and TripAdvisor (community, reviews).
- **What it includes:**
  - an **AI travel assistant**
  - car rental
  - city drivers
  - a "livreur" (delivery) service
  - Q&A / community
  - essentials (emergency numbers, Darija phrasebook, currency)
- **Traffic source:** the app is a traffic source for the owner's WordPress website **https://comemorocco.com**.
- **Money:**
  - **Now:** affiliate links (GetYourGuide, Booking.com, Travelpayouts partners, car rental, transfers).
  - **Later:** a **commission system like Booking/GetYourGuide**. Providers (riads, drivers, tour operators) list directly. When a client books through the app, the commission comes to ComeMorocco automatically, and the provider knows the client came from ComeMorocco.
- **Constraints from the owner:**
  - Cheapest good stack.
  - **Free LLM models only**, via **OpenRouter** and **Cloudflare Workers AI**.
  - Modern design.
  - 4 languages: **English, French, Spanish, Arabic (RTL)**.
- **Official spec:** `docs/MASTER_PLAN.md` (condensed from the owner's "Master Product & Technical Development Plan", sections 1–62). Follow it. Key rules:
  - RLS on every table
  - report/block/moderation before community
  - AI never the only moderation layer
  - AI actions validated, payments always confirmed
  - guest mode first, sign-in optional

## 2. Repository layout (pnpm monorepo, `node-linker=hoisted`)

| Path | What |
|---|---|
| `apps/mobile` | Expo **SDK 57** app, Expo Router (`src/app`), React 19, RN 0.86, React Compiler. Tabs: Explore, Book, AI, Community, My Trip. |
| `services/ai` | The **ComeMorocco AI** service: Python 3.11+ FastAPI, retrieval over the site's content + affiliate map, provider fallback chain, streaming SSE. Originally the owner's `comemorocco-ai.zip`. |
| `workers/platform` | Cloudflare Worker (Hono): `/go/:listingId` affiliate redirect (adds sub-id, logs clicks, no open redirect), `/v1/content` WordPress ingestion with cache, `/health`. |
| `packages/shared` | Versioned **v1 contracts** (zod mirroring the AI's Pydantic schemas), AI client (`streamChat` with SSE + JSON fallback), `authorizeToolCall`, analytics event taxonomy, contract examples exported from the real service. |
| `packages/i18n` | en/fr/es/ar messages, type-enforced keys (every key must exist in all 4). |
| `packages/ui` | Design tokens with a WCAG AA contrast test. |
| `supabase/` | `migrations/` (7 files), `seed/`, `tests/` (RLS tests with a shim), `setup/all-in-one.sql` (one file for a new project's SQL Editor; built by `scripts/build-supabase-setup.sh`). |
| `scripts/` | `generate_catalog.py` (catalog from the AI knowledge base, `--check`), `fetch_page_images.py` (photos from the site), `test-supabase.sh`, `check-supabase-live.mjs`, `scan-secrets.mjs`, `build-supabase-setup.sh`. |
| `docs/` | `MASTER_PLAN.md`, `architecture.md`, `ai-audit.md`, milestone notes `foundation-v0.1.md`, `milestone-v0.2/0.3/0.4.md`, `run-on-phone.md`, `screenshots/`. |
| `.github/workflows/ci.yml` | 4 jobs: AI (pytest, hash-seed determinism, eval gate, contract check, ruff on new files), TypeScript (typecheck, lint, tests, catalog `--check`), Supabase (Postgres 16 + RLS tests), secret scan. |

**Checks to run before every push:**
```bash
pnpm typecheck && pnpm lint && pnpm test
python3 scripts/generate_catalog.py --check
scripts/test-supabase.sh
node scripts/scan-secrets.mjs
cd services/ai && .venv/bin/python -m pytest -q && make eval-gate && .venv/bin/python scripts/export_contract_examples.py --check
```
Note: `pnpm -s typecheck` hides errors; use `pnpm typecheck` and check the exit code.

## 3. Services, accounts and keys

**Secrets are NEVER committed.** Here is where each one lives:

| Service | Used for | Where the key lives |
|---|---|---|
| **Supabase** project `vsswwdauxyjsefuhvtgr` (`https://vsswwdauxyjsefuhvtgr.supabase.co`) | Auth (email code), database, RLS | **Publishable key** (`sb_publishable_…`, public by design) in `apps/mobile/.env.local` as `EXPO_PUBLIC_SUPABASE_ANON_KEY` (gitignored). **Secret key** (`sb_secret_…`): server-only. It was pasted in chat once, so the owner should roll it in Supabase → API Keys. Never put it in the app. |
| **OpenRouter** | Free LLMs | `OPENROUTER_API_KEY` in `services/ai/.env` (gitignored; on the owner's Mac too). Free tier ≈ 50 requests/day; $10 one-time credit → ≈ 1,000/day. |
| **Cloudflare Workers AI** | Fallback LLMs | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` in `services/ai/.env`. ≈ 10k Neurons/day free ≈ 130 Mistral answers. |
| **Unsplash** (app id 953669) | Photos in AI answers | `UNSPLASH_ACCESS_KEY` in `services/ai/.env` (server-side only). The secret key isn't needed (it was shown in chat; regenerate if wanted). Demo limit 50 req/hour; results cached 24 h. Guidelines: hotlink `images.unsplash.com`, credit photographer + Unsplash with links (`utm_source=comemorocco&utm_medium=referral`). |
| **Brevo** (SMTP) | Supabase auth emails | Configured in Supabase → Authentication → Emails → SMTP: host `smtp-relay.brevo.com`, port 587, login `bc015c001@smtp-brevo.com`, password = Brevo SMTP key (only in Supabase). Sender `brahimabbar2005@gmail.com` (verified). Free 300 emails/day. |
| **WordPress** comemorocco.com | Content, guides, activity pages, photos (og:image) | Public REST API. Hosted on Hostinger. |
| **GitHub** | Code | `brahimabbar2005-lab/my-app` |

**AI model chain** (`LLM_CHAIN` in `services/ai/.env`):
```
openrouter:nvidia/nemotron-3.5-lightning:free,workers_ai:@cf/mistralai/mistral-small-3.1-24b-instruct,workers_ai:@cf/meta/llama-4-scout-17b-16e-instruct
```
With `OPENROUTER_REASONING_EFFORT=off`, `TEMPERATURE=0.4`, `MAX_ANSWER_TOKENS=1400`. The router:
- falls through before the first shown token
- has a 10 s first-token timeout and a 45 s provider timeout
- holds back a 120-character probe to catch garbled output
- applies per-failure cooldowns

**The owner's Mac setup** (see `docs/run-on-phone.md`): the project is cloned at `~/comemorocco`. Each service runs in its own Terminal tab:
- **AI:** `cd services/ai && source .venv/bin/activate && make run-lan`
- **App:** `pnpm mobile --clear`, then scan the QR code with **Expo Go** (Android phone)
- **Link worker:** `pnpm worker:lan`

The phone must be on the same Wi-Fi. In development the app maps `localhost` service URLs to the Mac's LAN IP (`apps/mobile/src/lib/dev-host.ts`). The Mac's own `services/ai/.env` holds the provider keys.

**Cloud dev container notes** (Claude Code on the web):
- Allowed network domains include `openrouter.ai`, `api.cloudflare.com`, `comemorocco.com`, `*.supabase.co`. `api.unsplash.com` / `images.unsplash.com` were **not** allowed: Unsplash tests use mocks.
- Metro's file watcher sometimes misses edits. Restart Expo with `--clear`, and kill only processes whose cmdline doesn't contain bash: `pkill -f` kills your own shell.
- Use `EXPO_OFFLINE=1` for `expo install`/`start`.

## 4. Live Supabase state

Already run in the owner's project, in order:
1. `supabase/setup/all-in-one.sql`: the foundation, RLS, account functions, trip sync, localized taglines, seeds (11 destinations, 77 listings).
2. `20261001000006_community.sql`
3. `insert into admin_users` with the owner's user id `dfa04fe2-5361-4c29-a604-26297776e864` (the owner is admin).

**Pending for the owner:** run `20261002000007_admin_catalog.sql` in the SQL Editor (needed for Manage offers and hotels/riads). Check whether they did it.

Auth emails:
- The "Magic Link" template contains `{{ .Token }}`.
- The "Confirm signup" template should also contain `{{ .Token }}`; ask if it was done.
- Site URL: `https://comemorocco.com`.

## 5. What is built (milestones)

**v0.1 Foundation**
- Monorepo, contracts, i18n, design tokens.
- Expo shell with 5 tabs.
- Onboarding (dreaming / planning / in Morocco + interests).
- Settings: language, theme, privacy, data export, delete content, delete account.
- AI service imported and hardened: provider router, app key / Supabase JWT auth, rate limits.
- Worker `/go`, Supabase schema + RLS + tests, CI, secret scan.

**v0.2**
- AI: French/Spanish retrieval (lexicon bridge, accent folding), localized fallbacks, deterministic retrieval.
- **My Trip:** local-first, synced via `sync_trip` RPC when signed in. Days, items, notes, travellers, share.
- AI ↔ trip context. AI proposes validated actions (`add_to_trip`, `save_place`) as buttons.
- Interest-filtered guides, localized taglines.

**Live connection**
- Supabase connected.
- Sign-in with a 6-digit email code (`verifyOtp`) or a link.
- Web SSR fix.
- `scripts/check-supabase-live.mjs`.

**v0.3 Community + moderation**
- Feed by type (question / trip report / tip) and city; post screen with replies, votes, report (reason picker), block; compose.
- Database screening: links >2, scam keywords like `wa.me/`, crypto, Western Union; rate limits. Held posts go to `pending` with a `content_flags` row.
- 3 distinct reporters auto-hide a post.
- `moderation_queue()` / `moderate()`, audited; admin moderation screen.

**Phone-testing round** (fixes from the owner's Expo Go tests)
- Photos come from the site's own og:images, ~768 px copies (`apps/mobile/src/data/images.generated.json`). Activities get the best-matching page photo.
- Removed a dead guidelines link.
- Dev error detail (`[dev] address: reason`).
- AI photos from Unsplash with credits when the traveller asks to see a place (en/fr/es/ar).

**v0.4**
- **Near me:** expo-location → nearest city. Only the city is used; the position is never stored.
- **City page photos.**
- **Keyboard:** the AI composer is lifted by keyboard height − tab bar height (+ Android nav bar). Still being confirmed on the phone.
- **"Add this N-day plan to My Trip"** button parses Day/Days/Jour/Día/اليوم lines (`lib/itinerary.ts`, `applyPlan`). The AI is forbidden to claim it saved anything.
- **Inline links in AI answers** to site pages: activity words and city names, first mention, max 6 (`lib/autolink.ts`). Only our own URL list is ever linked.
- **Admin catalogue** (`admin_listings()`, `admin_save_listing()`):
  - offer types: hotel, riad, hostel, guesthouse, camp, apartment, villa, tour, day_trip, activity, class, car, transfer, driver
  - photo, price, direct or partner link, draft/published/archived
  - screens: Profile & settings → Manage offers
- **Book tab and city pages** merge live Supabase offers with the bundled ones (`lib/listings.ts`). Type chips, city chips, prices.

**Test counts at handoff:** AI 219 pytest; TS tests across packages (mobile ~35); RLS tests with ~40 checks; all green.

## 6. Known issues / to verify with the owner

- **Keyboard:** confirm on the owner's Android phone that the AI input is fully above the keyboard.
- **AI speed:** it's slow-ish, because of the free models.
- **Partner links on the phone:** "View options" needs the link worker running. On the Mac that's `pnpm worker:lan`. Admin-added *partner* links also need the worker to have `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`, in `workers/platform/.dev.vars` locally or as Cloudflare secrets when deployed.
- **Ouarzazate** has no guide page on the site, so no photo.
- 45 site photos are still full-size (1.5–2.5 MB).
- `/morocco-travel-cost-guide/` returns HTTP 500 on the site.
- **Missing WordPress pages:** `/account-delete/` (required by Google Play) and `/affiliate-disclosure/`. Texts were given to the owner; ask if they were created.
- **Book tab:** when it's already open, navigating to it with new params (city/category) doesn't change the filters. Minor.

## 7. What to do next (priority order)

1. **Host the AI and the link worker in the cloud** (cheapest), so the app works anywhere without the Mac:
   - **Worker:** `wrangler deploy` to the owner's Cloudflare (free), set secrets `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`, and set `EXPO_PUBLIC_PLATFORM_URL`.
   - **AI:** FastAPI needs a Python host (e.g. a free/cheap container host). Set its env from `services/ai/.env.example`, set `EXPO_PUBLIC_AI_URL`, and add CORS for the site widget.
2. **Logo and store builds.** The owner will generate a logo from the prompt given (zellige 8-point star with a map-pin centre, deep green `#0F3D2E` + saffron gold `#E3A72F`). Files needed:
   - `icon.png` 1024²
   - `adaptive-foreground.png` 1024² (symbol inside the central 680²)
   - `monochrome.png`
   - `splash-icon.png`
   - Play icon 512²
   - feature graphic 1024×500

   Then wire them into `app.json` and set up EAS build (`eas.json`), plus store listings.
3. **Commission and booking system** (Master Plan): provider accounts (`providers`/`provider_users` tables exist), provider dashboard to manage offers and availability, booking requests (`bookings` tables exist), payments with confirmation, commission tracking and payouts, "came from ComeMorocco" attribution for providers. Affiliate conversions (`affiliate_conversions`/`affiliate_commissions` tables exist) via partner postbacks.
4. **City driver, car rental, livreur:** currently "coming soon". Needs driver profiles (admin-added first via Manage offers, category driver), request/booking flow, WhatsApp/contact.
5. **Reviews and ratings** on offers. **Photos in community posts** (`community_media` + Storage rules + image moderation). AI citing community posts.
6. **Push notifications** (tables exist), **offline maps/essentials**, **analytics dashboard**.
7. **Unsplash for more surfaces:** a city with no site photo (Ouarzazate), admin "pick a photo" helper.
8. **Production hardening:**
   - rotate the keys exposed in chat (Supabase secret, Unsplash secret; consider OpenRouter/Cloudflare too, which appeared in a screenshot)
   - Sentry/crash reporting
   - rate limits on the deployed AI
   - privacy policy updates for location and photos

## 8. Conventions

- Match the surrounding code style. Keep pure logic in `*-model.ts` / pure modules with vitest tests in `apps/mobile/test/`. Unit tests can't import `supabase.ts`.
- New UI strings go in **all 4 locales** (`packages/i18n/src/locales/{en,fr,es,ar}.ts`). Admin/staff screens may be English only.
- DB changes: add a new migration file. Add RLS tests to `supabase/tests/rls.test.sql`. Rebuild `supabase/setup/all-in-one.sql` with `scripts/build-supabase-setup.sh` and verify it on an empty Postgres. Give the owner the single new migration file to run in the SQL Editor.
- AI contract changes: update Pydantic (`services/ai/app/schemas.py`) and zod (`packages/shared/src/api/v1/chat.ts`), then run `services/ai/scripts/export_contract_examples.py`.
- Free models only for the AI. No model identifiers in commits.
- Commits end with the session attribution lines the environment provides. Push to `claude/gifted-franklin-puuz00`. No PR unless the owner asks.
