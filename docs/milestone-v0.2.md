# Milestone v0.2 — status

Master Plan phases touched: **2** (content/Explore), **4** (AI integration), **5** (My Trip).
Built as vertical slices (§51): each has storage → API/contract → app → tests.

| | Screens |
|---|---|
| ![AI in French with trip actions](screenshots/ai-fr-actions.png) | ![My Trip](screenshots/my-trip.png) |

## What shipped

### 1. AI language quality (Phase 4)
- **The bug.** French and Spanish questions missed the English content, and the intent and affiliate rules. `app/core/lexicon.py` fixes this with a deterministic bridge:
  - accent folding
  - English equivalents of known travel phrases
  - "de X à Y" routes

  It applies only to messages detected as French or Spanish, so English behaviour is unchanged.
- **Fallback messages** are now in English, French, Spanish, Arabic and Darija.
- **A pre-existing English bug was found and fixed:** "desert tour from Marrakech" offered waterfall day trips.
- **Evidence:** `tests/test_multilingual.py`, 18 cases, all of which failed before the change. The eval is unchanged.

### 2. My Trip, local-first (Phase 5)
- **Pure model** (`apps/mobile/src/lib/trip-model.ts`):
  - days, ideas, reorder across days, day-count changes that never lose items
  - saved places, a share-as-text itinerary, AI trip context
  - row mapping onto the Supabase tables, tested against the migration's actual columns
- **Store** (`trip-store.tsx`):
  - guests plan on the device
  - signed-in travellers sync through `sync_trip()`, which is atomic and RLS-checked; a device trip is uploaded on first sign-in
- **UI:**
  - the Trip tab: name, days and travellers steppers, a day-by-day itinerary with up/down reorder, ideas you plan onto a day, notes, saved places, share, and delete with confirmation
  - "Add to My Trip" and save (heart) buttons on listings, destination tiles and destination pages
- **Database:** migration `20260930000004_trip_sync.sql`, with RLS tests where a user syncs their own trip and another user fails to overwrite it.

### 3. AI trip context + validated actions (Phase 4, §13–14, §19–20)
- **Trip context in.** `ChatRequest.trip_context` carries the traveller's trip. It fills gaps in the conversation's trip state and never overrides what the traveller said (exclusions win).
- **Proposals out.** `ChatResponse.actions` / stream `meta.actions`: `add_to_trip` for each selected card, and `save_place` for detected destinations. They're built by code, the service never writes user data, and nothing is proposed for off-topic, safety or problem messages.
- **App side.** Each action becomes a button. A tap goes through `authorizeToolCall` (schema, permission, `userRequested`), and only then runs against the trip store. A `deviceLocal` rule lets guests write their own on-device trip; payments still require an account and confirmation.
- **Cross-language guard.** A contract test takes the actions the real service proposes and checks that each passes the app's validator.

### 4. Content polish (Phase 2)
- Destination taglines in en/fr/ar/es (catalog, seed, and `destinations.tagline` → jsonb migration).
- Explore's fallback guides are ordered by the traveller's onboarding interests.
- French and Spanish tab labels shortened (Forum / Voyage / Foro) so all five fit at phone width; web tab bar no longer clips labels.

## Verification
| Check | Result |
|---|---|
| AI tests | 180 passed (153 → 180) |
| AI eval gate | affiliate 0.958 · link 1.000 · live-data 0.638 · retrieval 0.378 (unchanged) |
| TypeScript: typecheck, lint | ✅ all packages |
| TypeScript tests | ui 28 · i18n 5 · shared 19 · worker 12 · mobile 21 |
| Supabase migrations + RLS (empty Postgres 16) | ✅ including trip-sync ownership and localized taglines |
| Contract examples regenerated from the real service and checked on both sides | ✅ |
| Secret scan | ✅ |
| Browser end-to-end (Playwright against the running AI service, worker and Expo web) | **15/15** — see below |

End-to-end checks (`scratchpad/e2e-v02.mjs`, run against the live local stack):
- French desert question → Sahara/desert guides, no hammam guide, desert-tour partner cards, French fallback text
- 4 "Add to My Trip" actions shown; tapping one marks it "in your trip" and it appears on the Trip tab, persisting across reload
- building a trip from destination pages, planning ideas onto Day 1 and reordering them
- the trip is sent to the AI as `trip_context`
- the Arabic tagline shows on the destination page in dark mode

## Still blocked by the build environment
`make check-model` was retried with the provided OpenRouter and Cloudflare keys. Both calls were refused by this container's network proxy (HTTP 403 from the proxy; the providers were never reached). Allow `openrouter.ai` and `api.cloudflare.com` under the environment's Network access to see live answers here. Everything else about the model chain is tested with mocked HTTP.
