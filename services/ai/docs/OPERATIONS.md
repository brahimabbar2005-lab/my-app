# Operations

## Deploying

```
comemorocco.com (WordPress)        ai.comemorocco.com (this service)
  plugin renders the widget   ──►    FastAPI behind nginx
  plugin exports content      ◄──    scripts/wp_sync.py
```

Run it anywhere that runs a Python process: a small VM, Fly.io, Railway,
Render, ECS. It is one stateless process plus Postgres.

```bash
gunicorn app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 2 --bind 0.0.0.0:8000 --timeout 120
```

Two workers is plenty to start. `--timeout 120` matters: a long itinerary
answer can take a while, and the default would cut the stream.

**nginx must not buffer SSE.** The service sets `X-Accel-Buffering: no`, but
check the server block too:

```nginx
location /api/chat/stream {
    proxy_pass http://127.0.0.1:8000;
    proxy_buffering off;
    proxy_read_timeout 180s;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

Without this the answer arrives in one block at the end and the widget looks
broken.

## Environment

Set in production: `ANTHROPIC_API_KEY`, `DATABASE_URL`, `WIDGET_KEY`,
`ADMIN_KEY`, `SYNC_SECRET`, `CORS_ORIGINS`, `ENVIRONMENT=production`.

While `ADMIN_KEY` is unset every admin endpoint returns 503 — fails closed.

## Installing the plugin

1. Copy `wordpress-plugin/comemorocco-ai/` to `wp-content/plugins/`.
2. Activate it. **Settings → ComeMorocco AI.**
3. Set the service URL and the widget key (matching `WIDGET_KEY`).
4. Copy the generated sync secret into the service's `SYNC_SECRET`.
5. Tick "Show the assistant" only once the health banner is green.

The settings page live-checks `/health` and reports how many pages are
indexed, so a wrong URL is visible there rather than discovered by a visitor.

After any change to the widget, re-copy it:

```bash
cp widget/comemorocco-ai.js wordpress-plugin/comemorocco-ai/assets/
```

## Scheduled jobs

```cron
0 3 * * *  curl -sS -X POST $SERVICE/api/admin/purge -H "X-Admin-Key: $ADMIN_KEY"
30 3 * * * cd /srv/comemorocco-ai && python scripts/wp_sync.py --admin-key $ADMIN_KEY
```

Publishing a post also pings `/api/admin/content-changed`, which reindexes
what is on disk. The nightly sync is what refreshes that disk copy, and the
backstop if a ping is missed.

## Weekly routine

```bash
curl -s $SERVICE/api/admin/stats -H "X-Admin-Key: $KEY" | jq
```

Watch: helpful rate, messages per conversation, average latency, flagged
count, daily tokens.

**Moderation queue** — `/api/admin/flagged` holds answers that failed a check
or got a thumbs down, with the retrieval trace attached. Resolve each as
`approved`, `corrected` or `ignored`. A pattern here is usually a prompt or
retrieval problem, not a one-off.

**Content gaps** — `/api/admin/content-gaps`, ordered by frequency. This is
the editorial brief list. A question appearing 50 times with no page behind it
is an article worth writing, and writing it improves both SEO and the
assistant.

## Before changing the prompt or model

```bash
make eval                                                  # deterministic, fast
python -m eval.harness --limit 40 --rubric --out eval/reports/candidate.json
python -m eval.harness --compare eval/reports/baseline.json
```

Never ship because a new model "feels better" — the blueprint is explicit on
this. The comparison marks any scorer that drops more than 0.02 as a
regression.

Keep a baseline report in the repo and update it deliberately.

## Cost control

Two models: the answer model for prose, a small model for classification,
extraction and quality review. Retrieval costs nothing.

If spend runs high:
- lower `DAILY_TOKEN_BUDGET` (it fails closed)
- lower `RATE_LIMIT_PER_DAY`
- lower `MAX_HISTORY_TURNS`
- set `QUALITY_CHECK_ENABLED=false` — saves a call per message, at the cost of
  the strongest guard against fabricated experience. Prefer the other levers.

## Troubleshooting

**Answers arrive all at once** — nginx is buffering. See above.

**Widget does not appear** — check "Show the assistant" is on, the path is not
excluded, the post type is ticked, and consent has been granted if required.

**401 from the API** — `WIDGET_KEY` and the plugin's widget key disagree.

**"I couldn't get that answer together"** — the model is unreachable. Check
`/health` for `model_configured`, then the key and the provider status.

**Links point at deleted pages** — `wp_sync.py` has not run since the page was
removed. Run it; it prunes on a full sync.

**A new article is never recommended** — expected. New pages are marked
`needs_review` and are not proactively linked until classified. `wp_sync.py`
lists them on every run.
