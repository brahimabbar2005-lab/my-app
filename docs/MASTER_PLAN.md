# ComeMorocco Travel Super-App — Master Product & Technical Development Plan

> The official specification for this repository, approved by the product owner (September 2026).
> Condensed into reference form from the approved text: every section and rule is kept, and the
> explanatory examples are shortened. Implementation status lives in [`foundation-v0.1.md`](foundation-v0.1.md).

- **Platforms:** iOS + Android
- **Primary app:** ComeMorocco
- **Website:** comemorocco.com
- **Development model:** Expo + React Native + TypeScript
- **Backend:** Supabase + Cloudflare Workers + FastAPI AI service
- **Primary objective:** Build a Morocco-focused travel platform that helps users discover, plan, book, experience and share Morocco.

**The crucial principle:** the AI does not own the application. The platform owns the application; the AI is an intelligent service operating inside controlled boundaries.

**Strategic framing:** build the ComeMorocco platform first, with the mobile app as its first client.

```
                    COMEMOROCCO PLATFORM
                           │
       ┌───────────────────┼───────────────────┐
     Website             Mobile               AI
       └───────────────────┼───────────────────┘
                  Common data + APIs
        ┌──────────────────┼──────────────────┐
     Travelers          Providers         Community
        └──────────────────┼──────────────────┘
                    BOOKING / REVENUE
```

---

## 1. Product vision
ComeMorocco is not only a booking app. It is a Morocco travel companion covering the complete traveler lifecycle:

`Thinking about Morocco → Discover → Plan → Book → Arrive → Explore → Ask AI → Get local help → Share experience → Return / recommend`

The product combines:
- Morocco travel content
- hotels and riads
- tours and activities
- car rental
- transfers and drivers
- a traveler community
- personalized trip planning
- an AI travel concierge
- local travel information
- affiliate booking
- a future direct-provider marketplace

The mobile app and comemorocco.com must operate as one ecosystem.

## 2. Core product principle
The platform owns traveler, trip, content, booking and community data. The AI is an intelligent service that consumes controlled context and can perform explicitly permitted actions. The AI must never become the system of record.

## 3. Architecture
```
                         COMEMOROCCO ECOSYSTEM
       comemorocco.com       iOS + Android       Future Channels
         WordPress              Expo             Web / WhatsApp
                                  │
                         COMEMOROCCO PLATFORM
      Users           Trips    Content    Booking      Community
                                  │
                        COMEMOROCCO AI ORCHESTRATOR
                                  │
         Knowledge            Context                Tools
         WordPress RAG        User profile           Maps
         FAQs                 Trip                   Weather
         Activities           History                Transport
         Affiliates           Preferences            Booking, Community
                                  │
                        ANSWER / RECOMMEND / ACT
```

## 4. Monorepo
`apps/mobile`, `apps-admin/admin`, `apps-provider/provider-portal`, `services/ai`, `packages/{shared,ui,config,i18n}`, `supabase/{migrations,seed,functions,config}`, `workers/platform`, `docs`, `scripts`. The existing comemorocco-ai service must be imported without unnecessary rewrites.

## 5. Technology stack
- **Mobile:** Expo, React Native, TypeScript, Expo Router, NativeWind, Reanimated, Moti, expo-image, Expo Notifications, i18n, RTL.
- **Backend:** Supabase (PostgreSQL, Auth, Storage, Realtime, RLS).
- **API / infrastructure:** Cloudflare Workers, Hono, Cloudflare Cron where appropriate.
- **AI:** the existing FastAPI service. Providers are OpenRouter, Workers AI, Anthropic and future providers, behind a provider abstraction with fallback routing.
- **Content:** WordPress REST API, ComeMorocco editorial content, a structured content cache, RAG.
- **Maps:** a map abstraction with a configurable tile provider. Never hard-code the public OpenStreetMap tile servers. Attribution and usage terms must be respected.

## 6. Cost strategy
Development/MVP should run as close to zero monthly cost as reasonably possible, using free tiers. Production must not assume services stay free: free infrastructure now, portable architecture, paid infrastructure later, with no rewrite.

Free-tier notes (September 2026):
- **Supabase Free:** pauses after about 7 days of inactivity. It is for development and MVP only.
- **Workers Free:** 100k requests/day, 10 ms CPU.
- **Workers AI:** 10k Neurons/day, and some models need Workers Paid.
- **OpenRouter free:** 50 requests/day without credit.
- **Koyeb free instance:** for testing and hobby use only.
- **Cloud Run:** free tier, but needs billing configured.

## 7. App navigation
Bottom navigation: **Explore | Book | AI | Community | My Trip**. Profile and settings are reached from the avatar.

## 8. Explore
The main home screen. It adapts to the trip stage (Dreaming / Planning / In Morocco) and covers:
- search and destination discovery (Marrakech, Fes, Chefchaouen, Merzouga, Essaouira, Casablanca, Rabat, Tangier, Agadir, Ouarzazate, Dakhla)
- seasonal ideas and popular activities
- ComeMorocco articles and community stories
- nearby content, when location is enabled

The feed must be data-driven.

## 9. Book
Stays, Experiences, Cars, Transfers, Drivers, Future Services. Each listing has:
- title, description, photos, destination, location, category, tags
- price indication, duration, rating where available
- provider, booking source, affiliate source
- cancellation information where available
- a booking CTA

The initial model is affiliate/external booking.

## 10. AI tab
A first-class surface. It covers:
- questions and recommendations
- destination discovery
- itinerary generation and trip modification
- content, activity and booking recommendations
- local help and contextual trip assistance

Actions such as *Save itinerary*, *Add to My Trip*, *View activities* and *View articles*.

## 11. AI architecture
Preserve the existing pipeline:

`language → intent → trip state → safety → retrieval → links → affiliate gating → generation → quality check`

Extend it to:

`request → auth/context → intent → trip state → safety → knowledge retrieval → tool selection → tool execution → recommendation → generation → quality check → action validation → response`

## 12. AI provider routing
`LLMProvider` has implementations for OpenRouter, Workers AI, Anthropic and future providers. Routing order:

OpenRouter free model A → OpenRouter free model B → Workers AI → graceful fallback.

The router must detect HTTP 429, model unavailable, timeout, provider error and quota exhaustion. It must track provider health, quota, latency, errors, cost and model. No model may be hard-coded as permanently guaranteed.

## 13. AI tool system
Explicit tools with strict schemas (Zod in TypeScript, Pydantic in Python):
- search: `search_content`, `search_destinations`, `search_activities`, `search_listings`, `search_community`
- context: `get_destination`, `get_user_profile`, `get_current_trip`
- live information: `get_weather`, `get_nearby_places`, `get_route`, `get_transport_options`, `get_affiliate_options`
- trip changes: `save_place`, `add_to_trip`, `remove_from_trip`, `update_itinerary`
- links: `open_article`, `generate_booking_link`

## 14. AI action authorization
Separate READ from WRITE:
- Read actions normally execute automatically.
- Write actions (`ADD_TO_TRIP`, `SAVE_PLACE`, `UPDATE_ITINERARY`) are allowed only when explicitly requested.
- `MAKE_PAYMENT` always requires explicit user confirmation.

Flow: proposed action → validator → permission check → confirmation if required → execute → audit log. Every tool execution is logged.

## 15. AI safety
The AI must not invent:
- emergency numbers
- visa requirements
- current prices, opening hours or availability
- transport schedules
- official policies or legal information

Time-sensitive information must come from structured or live sources. Taxi pricing and scam reports are labeled as estimates or reports.

## 16. AI evaluation
Affiliate discipline and link discipline remain regression gates. Add:
- intent, language, destination and trip-state accuracy
- recommendation relevance
- hallucination rate and citation accuracy
- safety
- tool selection, argument correctness and action authorization
- response quality and latency

Maintain golden questions for English, French, Arabic, Darija and Spanish, eventually 200–500. Every AI change runs the suite.

## 17. Traveler profile
Profile, language, currency, interests, travel style, budget, food, activity, accessibility and notification preferences. Learn them progressively; never force a long onboarding.

## 18. Guest mode
Guests can browse destinations, content and listings and use limited AI. An account is needed for saving, My Trip sync, community posting, booking management and personalization.

## 19. Authentication
Email, Google, Apple. In-app account deletion (Profile → Settings → Delete account) plus a web deletion resource.

## 20. My Trip
A trip has dates, travelers, budget, destinations, days, itinerary items, saved places, bookings, transport, notes and documents. The AI receives the current trip as controlled context.

## 21. Trip actions
Create, rename, add destination/place/activity, remove, reorder, modify dates, save booking, notes, share.

## 22. Affiliate system
Tables: `affiliate_programs`, `affiliate_links`, `affiliate_clicks`, `affiliate_conversions`, `affiliate_commissions`.

Flow: user → listing → `/go/:listingId` → Worker → record click → affiliate URL → partner.

Never expose affiliate configuration to the app.

## 23. Affiliate attribution
Capture, where available:
- `user_id`, `anonymous_id`, `trip_id`
- `listing_id`, `partner`, `sub_id`
- `source`, `campaign`, `platform`, `device`, `timestamp`

Conversion tracking supports API, webhook, CSV/report import and manual reconciliation. Never assume a partner exposes a conversion API.

## 24. Booking model
Affiliate states stay separate: `affiliate_click → affiliate_conversion → affiliate_booking → affiliate_commission`.

Direct bookings use their own tables: `booking`, `booking_item`, `payment`, `refund`, `commission`, `provider_settlement`.

## 25. Direct marketplace
Not before the payment and provider architecture is legally and technically validated. It needs:
- provider onboarding and KYC
- listings, availability and pricing
- booking, payment and refund
- commission, settlement, payout and invoice
- cancellation, no-show and dispute handling

Payment providers sit behind an abstraction (Moroccan PSP, international PSP, future). No PSP is assumed suitable before its current support is confirmed.

## 26. Direct booking flow
Request → provider accepts/declines → payment/deposit where supported → confirmed → booking code → completed → commission recorded.

Every state change is stored. States: pending, confirmed, declined, cancelled, completed, no_show, refunded, disputed.

## 27. Provider portal
Dashboard, profile, listings, pricing, availability, bookings, customers, commission, payouts, analytics, notifications, documents. Providers never access other providers' data.

## 28. Community
Posts, questions, answers, comments, votes, photos, trip reports, destination discussions. Later: meetups, messaging, follows.

## 29. Community moderation
Required from the beginning:
- reports, user blocks and content flags
- moderation actions, user suspensions and appeals
- the ability for users to report content, report users and block users

Moderation combines automatic flagging with human review. AI is never the only layer.

## 30. Reviews
Start with community experiences. Later add verified booking, visit and activity reviews. Community posts, reviews and provider responses stay separate.

## 31. Trip Mode
When the traveller is in Morocco:
- nearby attractions, restaurants and activities
- transport and local tips
- emergency information and the phrasebook
- their itinerary and saved places
- AI help

Location is optional, a manual city choice is always available, and location is requested only when a feature needs it.

## 32. Taxi / fair price
Never present AI estimates as official prices. Show an estimated range with source, date, route and vehicle type: *"Estimated travel reference — not an official tariff."*

## 33. Scam Radar
Built from community reports (location, date, behavior, count). Never label individuals or businesses as scammers. Wording is "Travelers have reported…".

## 34. Offline mode
Offline:
- the current trip, itinerary and saved places
- booking references
- emergency contacts, phrasebook and basic currency information
- downloaded destination content

Never promise live data offline.

## 35. WordPress integration
WordPress remains the editorial source. Flow: WordPress → ingestion/sync → content layer → AI + app.

Store `wordpress_post_id`, `canonical_url`, title, excerpt, image, categories, destination and `updated_at`. Link back to the canonical page.

## 36. Website ↔ app
Universal Links and Android App Links, e.g. `https://comemorocco.com/destinations/marrakech/`. The link opens the app if installed, otherwise the website.

"Read full guide" links carry `utm_source=app&utm_medium=mobile&utm_campaign=content`.

## 37. Community ↔ website
Community → moderation → editorial selection → WordPress. Never publish unmoderated user content automatically.

## 38. Map architecture
`MapService`, `GeocodingService`, `RoutingService` and `PlacesService`, each replaceable.

## 39. Notifications
Expo Notifications for:
- booking updates and provider responses
- trip and saved-trip reminders
- community replies
- AI trip reminders
- important travel alerts

Store `push_tokens` and notification preferences.

## 40. Analytics
A privacy-conscious event taxonomy:
- `app_opened`, `search_started`
- `destination_viewed`, `listing_viewed`, `article_opened`
- `ai_started`, `ai_message_sent`, `ai_recommendation_clicked`
- `trip_created`, `trip_item_added`
- `affiliate_clicked`, `affiliate_conversion`
- `community_post_created`, `community_post_viewed`
- `booking_started`, `booking_confirmed`

Events carry attribution properties.

## 41. Error monitoring
Sentry or equivalent for crashes, API errors, AI failures, navigation and booking failures. Never send unnecessary personal data.

## 42. Security
Required:
- RLS, JWT validation and rate limiting
- AI abuse protection
- upload limits
- webhook signature verification and idempotency keys
- audit logs and secret management

Never ship service-role keys, payment secrets, affiliate secrets, AI provider secrets or WordPress credentials inside the app.

## 43. Database
Core entities:
- **People:** users, profiles, preferences.
- **Catalog:** destinations, categories, places, listings (+ images, categories, locations).
- **Trips:** trips, trip days, trip items, saved places.
- **Providers:** providers (+ users, listings, availability).
- **Bookings:** bookings (+ items, status history).
- **Affiliate:** programs, links, clicks, conversions, commissions.
- **Community:** posts, comments, votes, media, reports, user blocks, moderation actions, badges, user badges.
- **AI:** sessions, messages, tool calls, feedback, usage.
- **Other:** notifications, push tokens, analytics events, emergency contacts, travel facts, price guides.

Future: payments, refunds, payouts, invoices, commission rules, provider settlements.

## 44. RLS
Every user-owned table has RLS:
- users: own profile only
- trips: owner only; trip items follow the trip owner
- saved places: owner only
- AI sessions: owner only
- bookings: the customer and the authorized provider
- provider listings: the provider owner
- community: public according to moderation status

Never rely only on frontend authorization.

## 45. Admin
An internal admin interface with these sections:
- Dashboard
- Users, Providers
- Destinations, Listings, Content
- Bookings, Affiliate
- Community, Reports
- AI, Analytics
- Settings

All admin actions are audited.

## 46. Design system
Moroccan, modern, premium, warm, travel-focused. Palette: terracotta, saffron, Majorelle blue, sand, mint, deep green, cream.

Don't overuse colors. The identity comes from photography, typography, subtle zellige patterns, icons, spacing and cards. Supports light and dark mode and RTL.

## 47. Internationalization
English, French, Arabic and Spanish, with German later. Arabic has full RTL (dates, numbers, navigation, layouts). AI language support is evaluated separately from UI translation. Darija is conversational in the AI, not a UI language.

## 48. Onboarding
Welcome → what brings you to Morocco (Dreaming / Planning / Already in Morocco) → optional interests → Explore. Never force account creation.

## 49. MVP
**Include:**
- Explore, destinations, activities, hotels/riads, articles
- affiliate links
- AI concierge and AI trip planner
- My Trip and saved places
- authentication and basic community
- push notifications, analytics and deep links

**Exclude:** livreur, live driver dispatch, real-time ride tracking, the full direct marketplace, complex payment splitting, meetups, full messaging, provider payouts.

## 50. Version roadmap
- **Phase 0 — Audit:** audit the existing AI; no rewrites without evidence.
- **Phase 1 — Foundation:** monorepo, Expo app, design system, navigation, i18n/RTL, Supabase, auth, RLS, migrations, Worker, CI.
- **Phase 2 — Content / Explore:** destinations, articles, activities, listings, search, filters, WordPress sync, deep links.
- **Phase 3 — Affiliate booking:** programs, mapping, `/go`, click tracking, attribution, partner adapters, analytics.
- **Phase 4 — AI integration:** auth, user and trip context, provider router, tools, actions, itineraries, cards, evaluations.
- **Phase 5 — My Trip:** trips, itinerary, saved places, AI modification, bookings, sharing, offline essentials.
- **Phase 6 — Community:** posts, Q&A, comments, votes, photos, reports, blocking, moderation, badges.
- **Phase 7 — Trip Mode:** optional location, nearby, map, local recommendations, emergency info, phrasebook, taxi references, contextual AI.
- **Phase 8 — Provider platform:** registration, profiles, listings, availability, requests, notifications, dashboard.
- **Phase 9 — Direct marketplace** (after payment and legal validation): payments, deposits, refunds, confirmation, commission, settlement, invoices, disputes, cancellation, no-show.
- **Phase 10 — Services marketplace:** drivers, transfers, car rental, guides, delivery, luggage and more.

## 51. Development order
Build in vertical slices (database → API → mobile → tests → analytics). Each slice must be independently testable.

## 52. First implementation
- **A.** Audit the AI without changing behavior (`make build`, `make test`, `make eval`) and record the baseline.
- **B.** Import it into `services/ai/`, preserving data, the source XLSX files, tests, evals and config. Keep secrets out of git.
- **C.** Scaffold the monorepo.
- **D.** Create shared, versioned schemas mirroring the Python contracts: ChatRequest, ChatResponse, ResourceCard, AffiliateCard, TripState, AIAction, ToolCall.
- **E.** Build the mobile shell with the five tabs on mock data.
- **F.** Connect the AI over `/api/chat/stream`. If SSE is unreliable on the runtime, provide an equivalent transport rather than coupling the architecture to one.
- **G.** Write the Supabase migrations, with RLS in place before features depend on the tables.
- **H.** Build the Worker's `/go/:listingId`: validation, affiliate resolution, click logging, UTM/sub-id, redirect, error handling.
- **I.** Add AI provider fallback (OpenRouter → OpenRouter → Workers AI) with health and quota handling.

## 53. Testing
- **AI:** `make build`, `make test`, `make eval` and `make check-model` stay green, and regressions below the baseline need approval.
- **Mobile:** `tsc --noEmit` and lint on Android, iOS and web, in light and dark mode, Arabic RTL, English and French.
- **Worker:** `wrangler dev`, then `GET /go/:id` validates, logs and redirects.
- **Database:** `supabase db reset` works from empty, with explicit RLS tests.

## 54. Security tests
Before launch, test:
- RLS bypass and JWT tampering
- unauthorized access to trips, bookings and provider data
- malicious uploads and spam
- AI prompt injection and tool abuse
- affiliate manipulation
- webhook replay, duplicate bookings and duplicate payments

## 55. Store readiness
- **Apple:** metadata, screenshots, privacy policy, account deletion, location disclosures, UGC moderation, support, terms, deep links, TestFlight.
- **Google:** listing, Data Safety form, account deletion, UGC moderation, privacy policy, internal and closed testing.

## 56. Privacy
Documents: privacy policy, terms, community guidelines, cookie policy, affiliate disclosure, provider terms, booking and cancellation terms.

Data to document: location, profile, AI conversations, trips, community content, photos, analytics, affiliate tracking, bookings and payments. Provide account and data deletion.

## 57. Production observability
Track API and AI latency, provider failures, token usage, affiliate clicks and conversions, booking and payment failures, crashes, database errors and notification failures. Alert on critical failures.

## 58. Business metrics
Track:
- DAU and MAU
- trip creation rate, AI usage and AI → trip conversion
- listing views, affiliate CTR and conversion
- revenue per traveler
- community engagement and retention

The long-term metric: a traveller uses ComeMorocco, plans, books, returns during the trip and recommends it.

## 59. Product north star
*"I don't need to figure Morocco out alone."* Useful before, during and after the trip.

## 60. Non-negotiable engineering rules
1. Do not rewrite the existing AI without an audit.
2. Do not put secrets in the mobile app.
3. Do not trust frontend authorization.
4. Use Supabase RLS.
5. Version API contracts.
6. Validate all AI tool arguments.
7. Require confirmation for payment and destructive actions.
8. Log AI tool calls.
9. Make affiliate integrations provider-specific.
10. Never assume affiliate conversion APIs exist.
11. Keep payment providers behind an abstraction.
12. Do not hard-code a map provider.
13. Do not treat OSM public tiles as unlimited free commercial infrastructure.
14. Do not publish unmoderated community content to WordPress.
15. Implement report/block/moderation before community launch.
16. Implement account deletion before store submission.
17. Do not request location before it is needed.
18. Never present AI estimates as official prices.
19. Do not promise live information without a live source.
20. Keep the application portable between free and paid infrastructure.

## 61. First developer deliverable — ComeMorocco Foundation v0.1
Audited AI service, monorepo, Expo shell, design system, 5-tab navigation, Supabase, initial schema, RLS, Worker, affiliate redirect, WordPress content connection, AI API connection, AI streaming, OpenRouter fallback, Workers AI fallback, shared schemas, baseline tests, CI checks.

Not included: direct marketplace payments, live drivers, delivery dispatch, the full provider marketplace, unnecessary rewrites.

## 62. Success criteria
The first milestone is complete only when all of these hold:
- AI tests pass, and the AI eval passes its baseline.
- Mobile TypeScript and lint pass.
- Worker tests pass.
- Supabase migrations pass, and the RLS tests pass.
- The AI streams, and resource and affiliate cards render.
- `/go` redirects correctly, and WordPress articles render.
- English, French and Arabic RTL work, and dark mode works.
- The app runs on Android and on iOS.
- No secrets are committed.
