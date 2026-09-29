# ComeMorocco AI — audit (Foundation v0.1, step A)

Audited from `comemorocco-ai.zip` before any change. Rule followed (Master Plan §60.1): nothing in the working pipeline was rewritten. Changes made afterwards are listed at the end.

## 1. What it is

A Python 3.11 FastAPI service (≈5,500 lines in `app/`) that answers Morocco travel questions. It returns resource cards (ComeMorocco pages) and, when the traveller is clearly trying to book, at most two affiliate cards.

| Area | Location | Notes |
|---|---|---|
| API | `app/api/routes_chat.py` | `POST /api/chat` (JSON), `POST /api/chat/stream` (SSE), `GET /api/starters` |
| Admin | `app/api/routes_admin.py` | stats, flagged answers, content gaps, reindex, purge, config. Guarded by `ADMIN_KEY` (503 while unset) |
| Pipeline | `app/core/orchestrator.py` | language → intent → trip state → safety → BM25 retrieval → link engine → affiliate gating → generation → quality check |
| Models | `app/core/llm.py` | Anthropic SDK + OpenRouter over httpx |
| Knowledge | `data/knowledge/*.json` | 240 pages, 14 destinations, 27 affiliate programs (26 usable), 77 activities (76 usable), 213 golden questions, 10 multi-turn tests |
| Storage | `app/db/` | SQLAlchemy. SQLite by default, Postgres via `DATABASE_URL` |
| Clients | `widget/`, `wordpress-plugin/` | Shadow-DOM widget and a thin WP plugin that renders it and exports content |

## 2. Baseline (recorded before changes)

| Check | Result |
|---|---|
| `pytest -q` | **115 passed** |
| `make eval` (offline, 213 questions) | affiliate_discipline **0.958**, link_discipline **1.000**, live_data_detection **0.638**, retrieval **0.378**, overall 0.744, 77 content gaps |
| `make check-model` | Not runnable from the build container: the network policy blocks `openrouter.ai` (HTTP 403 at the egress proxy, not from OpenRouter) |
| `ruff check app scripts eval tests` | 351 pre-existing findings (mostly style). Not fixed, to keep the import diff-free. New code is lint-clean |

`make eval` exits non-zero by design when individual golden questions fail. CI therefore gates on the **scores** (affiliate ≥ 0.958, link ≥ 1.000, live-data ≥ 0.638, retrieval ≥ 0.378) rather than on the exit code. See `scripts/check_eval_baseline.py`.

## 3. Strengths worth preserving

- **Code, not the model, decides links and affiliates** (`knowledge/links.py`, `knowledge/affiliates.py`). This is the basis of "relevance before revenue" and is regression-tested across the whole golden set.
- **Structured trip state**, including exclusions and hard constraints. This maps directly onto the app's My Trip.
- **Honest live-data boundary.** `LIVE_DATA_ENABLED=false` means the model is told it cannot check current conditions. This matches Master Plan §15.
- **Free-tier awareness.** On `:free` models it makes one call per question.
- **Cost and abuse controls.** Sliding-window limits keyed on both session and hashed IP, a daily token budget that fails closed, and length and repetition guards.

## 4. Findings

### Data (from the service's own README; still open)
1. Kiwi.com has no affiliate link (widget only). It is marked unusable.
2. 12 `gyg.me` short links are shared across 25 activities, so a Fes question could open an Agadir product. The links need verifying in the GetYourGuide dashboard.
3. Four widgets are configured for the wrong place: Hostelworld (New York), Klook `city_id=289`, Viator (fixed product), Localrent `country=99`.
4. The content map's `content_type` column is unreliable. One row (`/blog/`) is corrected at build time.

### Security / operations
1. `WIDGET_KEY` ships to browsers by design. It is friction, not authentication. The same applies to the new `APP_KEY`.
2. `client_ip()` trusts the first `X-Forwarded-For` hop. This is safe only behind a proxy that overwrites the header. Deploy behind one (Koyeb, Cloud Run and Cloudflare all do).
3. Rate limiting is in-memory and per-instance. That is correct for one instance, but a multi-instance deployment needs a shared store (the `Limiter` seam exists).
4. The admin endpoints are disabled unless `ADMIN_KEY` is set. That is good.
5. Dependencies use `>=` ranges with no lockfile. Pin them (`pip-compile` or `uv lock`) before production.
6. There were no user accounts: sessions were anonymous ids only. This is addressed below.

### Architecture gaps relative to the Master Plan
- Only one provider was active at a time, with no fallback (§12). **Addressed.**
- The service had no concept of a signed-in user (§18, §38). **Addressed** for identity and limits. Linking chats to Supabase `ai_sessions` is Phase 4.
- There is no tool or action layer yet (§13–14). This is Phase 4 work. Shared `ToolCall` / `AIAction` contracts are defined in `packages/shared` so the layer can be built against a fixed shape.
- Arabic, Darija and Spanish are detected but not claimed as supported (`SUPPORTED_LANGUAGES=en,fr`). They need golden questions per language before being enabled (§16).

## 5. Changes made in Foundation v0.1

All changes are additive. Existing callers of `complete` / `stream` / `complete_json` are unchanged.

| Change | Files |
|---|---|
| Provider abstraction: `LLMProvider`, `ProviderHealth` (requests, failures by kind, latency, tokens, cooldown) | `app/core/providers/base.py` |
| Existing Anthropic / OpenRouter code wrapped as providers (wire code untouched) | `app/core/providers/hosted.py` |
| Cloudflare Workers AI provider. The model is always set in config, with no hard-coded default | `app/core/providers/workers_ai.py` |
| Router: chain from `LLM_CHAIN` or from the configured keys. Skips providers in cooldown, falls through before the first streamed token (never mid-answer), and gives one combined error when all fail | `app/core/providers/router.py` |
| `ModelUnavailable.kind` (rate_limit / quota / auth / timeout / network / provider_error / empty / config) drives cooldown length | `app/core/llm.py` |
| `APP_KEY` accepted alongside `WIDGET_KEY` | `app/api/deps.py` |
| Supabase access-token verification (HS256 secret or JWKS). Invalid tokens are treated as guests | `app/infra/auth.py` |
| Signed-in callers limited per account at `SIGNED_IN_RATE_MULTIPLIER`× guest limits | `app/infra/ratelimit.py`, `app/api/routes_chat.py` |
| `GET /api/admin/providers` returns chain health. `/health` lists the chain | `app/api/routes_admin.py`, `app/main.py` |
| Tests: 34 new (router, Workers AI wire format, keys, JWT, limits) | `tests/test_provider_router.py`, `tests/test_app_clients.py` |

After the changes: **149 tests pass**, and the eval scores are identical to the baseline.
