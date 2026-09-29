# Architecture — Foundation v0.1

How the pieces in this repository fit together, and where each rule of the [Master Plan](MASTER_PLAN.md) is enforced.

```
            ┌───────────────┐      ┌────────────────────┐
            │ apps/mobile   │      │ comemorocco.com    │
            │ Expo (iOS,    │      │ WordPress + widget │
            │ Android, web) │      └─────────┬──────────┘
            └──┬─────┬───┬──┘                │ REST (read-only)
   /api/chat*  │     │   │ /go, /v1/content  │
   (SSE/JSON)  │     │   └──────────┐        │
               ▼     │              ▼        ▼
     ┌──────────────┐│      ┌───────────────────────┐
     │ services/ai  ││      │ workers/platform      │
     │ FastAPI      ││      │ Cloudflare Worker     │
     │ orchestrator ││      │ /go  /v1/content      │
     │ + provider   ││      └──────────┬────────────┘
     │   router     ││                 │ service role (server only)
     └──────┬───────┘│ anon key + RLS  ▼
            │        └────────► ┌───────────────────┐
            │  JWT verification │ Supabase Postgres │
            └─────────────────► │ RLS on every table│
                                └───────────────────┘
   OpenRouter free A → OpenRouter free B → Workers AI → graceful fallback
```

## Components

| Path | Runs on | Responsibility |
|---|---|---|
| `apps/mobile` | Expo (EAS builds for stores; web for previews) | Guest-first app: onboarding, Explore, Book, AI, Community, My Trip, settings, deep links |
| `services/ai` | Docker container (Koyeb free for dev → Cloud Run / paid for prod) | The existing ComeMorocco AI: pipeline, retrieval, link and affiliate engines, provider router |
| `workers/platform` | Cloudflare Workers | Affiliate redirects with click logging, cached WordPress content, health |
| `supabase` | Supabase (Free for MVP → Pro, no schema change) | System of record: users, trips, catalog, affiliate data, community, AI history, analytics |
| `packages/shared` | Imported by app, worker and (later) admin | Versioned v1 API contracts (zod), AI client, action authorization, analytics taxonomy |
| `packages/i18n`, `packages/ui` | Imported by app | Strings (en/fr/ar/es, RTL) and design tokens (AA contrast tested) |

## Data flows

### AI answer
1. The app posts `ChatRequest` to `/api/chat/stream` with `X-App-Key`, plus `Authorization: Bearer <supabase token>` when signed in.
2. The service verifies the token (`app/infra/auth.py`). Guests and invalid tokens get guest limits. Signed-in users get `SIGNED_IN_RATE_MULTIPLIER`× and are limited per account.
3. The orchestrator runs unchanged. Links and affiliates are chosen by code before generation.
4. Generation goes through `app/core/providers/router.py`, which tries each healthy provider in order and falls through on 429, quota, auth, timeout or 5xx. It only falls through *before* the first streamed token, never mid-answer.
5. SSE events are `meta` (cards) → `delta`* → `done`. The app renders resource cards as canonical comemorocco.com links with `utm_source=app`, and partner cards with their disclosure via `/go`.

If the runtime can't stream, `packages/shared/src/client/ai.ts` repeats the request on `/api/chat` and emits the same events.

### Affiliate click
1. The app opens `https://<worker>/go/<listingId>?src=<surface>&platform=…&aid=…`. It only ever knows listing ids.
2. The worker validates the id and resolves the partner URL from `affiliate_links` (service role) or the generated map.
3. It adds a click UUID as the network's sub-id (`sub_id` for Travelpayouts, `cmp` for GetYourGuide; confirm both in the partner dashboards).
4. It records `affiliate_clicks` via `waitUntil`, so the traveller never waits, then 302-redirects.
5. Unknown or malformed ids go to comemorocco.com. The worker never redirects to a URL outside its table.

Conversions arrive later via API, webhook, report import or manual reconciliation into `affiliate_conversions`, and are matched on the click UUID. Commissions are a separate state.

### Content
WordPress → `workers/platform /v1/content` (edge-cached 10 min) → app. If WordPress is unreachable, the worker returns an empty `fallback` list and the app shows its bundled catalog, generated from the editorial content map by `scripts/generate_catalog.py`. Nothing writes back to WordPress.

## Where the non-negotiables live

| Rule (§60) | Enforcement |
|---|---|
| 1. No AI rewrite without audit | `docs/ai-audit.md`; router added *under* the existing functions; eval baseline gate in CI |
| 2. No secrets in the app | `apps/mobile/src/lib/config.ts` only reads public `EXPO_PUBLIC_*`; the catalog bundle is tested to contain no partner URLs; `scripts/scan-secrets.mjs` in CI |
| 3–4. RLS, not frontend auth | `supabase/migrations/*_rls.sql`; `supabase/tests/rls.test.sql` (attack cases) |
| 5. Versioned contracts | `packages/shared/src/api/v1`; examples exported from the real service and parsed by zod and Pydantic |
| 6–8. Tool validation, confirmation, logging | `packages/shared/src/api/v1/actions.ts` (`authorizeToolCall`); `ai_tool_calls` table |
| 9–10. Provider-specific affiliates, no assumed APIs | `workers/platform/src/affiliates.ts` adapters; `conversion_capability` per program |
| 11. Payments behind an abstraction | No PSP code exists yet by design; bookings table is PSP-agnostic with idempotency keys |
| 12–13. No hard-coded maps / OSM tiles | No map dependency in v0.1; Trip Mode (Phase 7) adds a `MapService` with configurable tiles |
| 14–15. Moderation before community | Reports, blocks, flags, actions, suspensions, appeals tables + RLS exist; posting UI is disabled until the moderation queue is built |
| 16. Account deletion | `delete_my_account()` RPC + Settings screen + `comemorocco.com/account-delete/` link |
| 17. Location only when needed | "Near me" explains first and offers a manual city; no permission is requested in v0.1 |
| 18–19. No invented prices / live data | No prices shown; `price_guides` requires source + dates; emergency numbers ship "not yet verified" |
| 20. Portable free → paid | Every service is configured by URL/keys; no free-tier-only API is assumed |

## Environments

| | Development (now) | Production (target) |
|---|---|---|
| Database | Supabase Free (pauses after ~7 days idle) | Supabase Pro + scheduled backups |
| AI service | Koyeb free instance | Cloud Run or paid container |
| Worker | Workers Free | Workers Paid if CPU/requests require |
| Models | OpenRouter `:free` + Workers AI free allocation | Same chain; add OpenRouter credit or a paid model |
