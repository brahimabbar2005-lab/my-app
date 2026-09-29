# Foundation v0.1 — status against the success criteria

Master Plan §62 says the first milestone is complete only when every item below holds. This page records what was verified, how it was verified, and what could not be verified from the build environment.

**Summary:** 17 of the 19 items are verified. **App runs on Android** and **App runs on iOS** need a real device or simulator, which the Linux build container doesn't have; the web build of the same code was run and screenshotted. **AI streams** is verified end to end, but the answer text came from the service's fallback because the container's network blocks the model hosts.

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | AI service tests pass | ✅ | `services/ai`: `pytest -q` → **153 passed** (115 original + 38 new) |
| 2 | AI evaluation passes baseline | ✅ | `make eval-gate` → affiliate 0.958, link 1.000, live-data 0.638, retrieval 0.379 (baseline 0.378) |
| 3 | Mobile TypeScript passes | ✅ | `pnpm typecheck` (all 6 TS packages) |
| 4 | Mobile lint passes | ✅ | `pnpm lint` (eslint-config-expo) |
| 5 | Worker tests pass | ✅ | `workers/platform`: 12 tests; also run under `wrangler dev` |
| 6 | Supabase migrations pass | ✅ | `scripts/test-supabase.sh` applies all migrations + seeds to an empty Postgres 16 |
| 7 | RLS tests pass | ✅ | `supabase/tests/rls.test.sql`: cross-user reads/writes, moderation bypass, suspended users, affiliate data, analytics, account deletion |
| 8 | AI streams successfully | ✅ / ⚠️ | App → `/api/chat/stream` → meta/delta/done rendered. The answer text was the service's fallback, because model hosts are blocked from the build container (see below) |
| 9 | Resource cards render | ✅ | `docs/screenshots/ai-answer.png` |
| 10 | Affiliate cards render | ✅ | Same screenshot: two GetYourGuide desert tours with disclosure, opened via `/go` |
| 11 | `/go` redirects correctly | ✅ | `wrangler dev`: `GET /go/GYG-008` → 302 to `gyg.me/…?cmp=<click id>`, click logged; unknown id → comemorocco.com |
| 12 | WordPress articles render | ✅ / ⚠️ | Articles render from the catalog generated from the site's content map. The live `/v1/content` path is tested with mocked WordPress; the real site is blocked from the build container |
| 13 | English works | ✅ | `docs/screenshots/explore.png`, `book.png`, `destination.png` |
| 14 | French works | ✅ | French UI verified in the browser; all four locales are type-checked for completeness |
| 15 | Arabic RTL works | ✅ | `docs/screenshots/explore-ar-rtl.png`, `trip-ar-dark.png` (`<html dir="rtl">`, mirrored layout and tab order) |
| 16 | Dark mode works | ✅ | `trip-ar-dark.png`; every text/background pair tested for WCAG AA |
| 17 | App runs on Android | ⏳ | Needs a device or emulator: `pnpm mobile` → scan with Expo Go |
| 18 | App runs on iOS | ⏳ | Needs a device or simulator: `pnpm mobile` → scan with Expo Go |
| 19 | No secrets committed | ✅ | `node scripts/scan-secrets.mjs` in CI; `.env` and `.dev.vars` are gitignored |

## Blocked by the build environment, not by the code

The container's network policy denied `openrouter.ai`, `api.cloudflare.com` and `comemorocco.com`. Consequences:
- **`make check-model`:** it ran and walked the full chain (OpenRouter → Workers AI), but both calls were refused at the network proxy (HTTP 403 from the proxy, not from the providers). Run it once from a machine with normal internet to confirm the keys.
- **The model the Workers AI fallback uses (`WORKERS_AI_MODEL`)** could not be checked against the current free-plan model list. `@cf/meta/llama-3.1-8b-instruct` is set in the local `.env`; confirm it in the Cloudflare dashboard, and set `OPENROUTER_FALLBACK_MODEL` to a second `:free` model.
- **Live WordPress ingestion** (`/v1/content`) is implemented and tested against WordPress-shaped responses, and falls back cleanly when the site is unreachable.

## Known issues carried into the next milestones
- **French/Spanish retrieval and the English-only fallback message.** Recorded in `docs/ai-audit.md` §4 (items 7–8); belongs to Phase 4.
- **Destination taglines and emergency-contact labels are English only.** They are data, not UI strings, and move to Supabase with per-locale columns in Phase 2.
- **Sign-in:** email one-time links work once `EXPO_PUBLIC_SUPABASE_URL` and `EXPO_PUBLIC_SUPABASE_ANON_KEY` are set. Google and Apple need their native credentials and are shown as "coming soon".
- **NativeWind:** listed in the stack (§5). The app uses a typed token system (`packages/ui`) with React Native `StyleSheet` instead. NativeWind can be layered on later without changing the tokens.
- **Community posting** is off until the moderation queue (admin) exists, per §29 and §60.15. The tables and RLS for reports, blocks and moderation are already in place.
- **Legal pages must exist before store submission:**
  - `comemorocco.com/account-delete/`
  - `/privacy-policy/`
  - `/terms/`
  - `/affiliate-disclosure/`
  - `/community-guidelines/`

  The app links to all of them.

## How to reproduce every check
```bash
pnpm install
pnpm typecheck && pnpm lint && pnpm test          # TypeScript: app, worker, packages
python3 scripts/generate_catalog.py --check      # generated data is current
scripts/test-supabase.sh                          # migrations + RLS on empty Postgres
node scripts/scan-secrets.mjs                     # no secrets tracked
cd services/ai && pip install -r requirements-dev.txt && pytest -q && make eval-gate
python scripts/export_contract_examples.py --check
```
