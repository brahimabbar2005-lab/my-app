# Technical Design

Companion to `01_PRODUCT_BRIEF.md` §23, which asks for a technical design
document before development and says the design must not silently change the
product requirements. Where a requirement was interpreted rather than
implemented literally, it is called out under *Decisions that need sign-off*.

---

## 1. Shape

```
Browser (widget, Shadow DOM)
      │  POST /api/chat/stream          SSE
      ▼
FastAPI service
      │
      ├─ rate limiting + token budget   app/infra/ratelimit.py
      ├─ orchestrator                   app/core/orchestrator.py
      │     ├─ language / intent / trip state
      │     ├─ retrieval (in-memory BM25)
      │     ├─ link engine      ← decides, not the model
      │     ├─ affiliate engine ← decides, not the model
      │     ├─ generation (Anthropic)
      │     └─ quality check
      └─ Postgres (SQLite in development)

WordPress plugin ──► /api/admin/content-changed ──► reindex
scripts/wp_sync.py ──► pulls content export ──► rebuilds knowledge base
```

One process. No queue, no vector database, no separate worker. The MVP's load
does not justify them, and each would be a component to operate.

---

## 2. Why the knowledge base is a file, not a database

240 pages, 27 affiliate programs, 77 activities. Total 3.7MB of JSON.

Holding it in memory means retrieval costs no network call and no query. A
content update is a file swap plus `POST /api/admin/reindex`, which takes
milliseconds and needs no deployment. `KnowledgeBase.reload()` takes a lock so
this is safe while requests are in flight.

This stops being right at roughly 5,000 pages or when per-page permissions
appear. The `Retriever` interface is the seam: swapping in pgvector or a
search service changes one class.

---

## 3. Retrieval scoring

```
score = relevance + boosts

relevance = normalised_bm25 × (0.25 + 0.75 × coverage)
coverage  = matched terms / the 8 most discriminative query terms
```

**Why coverage.** Normalising BM25 by the top hit makes the best result score
1.0 even when nothing is relevant — "are there dinosaurs in Morocco?" would
score as highly as a perfect match. Coverage gives an absolute reading, so
"good match" and "no match" stay distinguishable. That distinction is what the
content-gap engine runs on.

**Why the 8 most discriminative terms, not all of them.** Travellers write
long posts. A 90-word question about Merzouga is still a question about
Merzouga, and requiring a page to echo 40% of ninety words marked every real
question a gap — 190 of 213 in the first run. Ranking query terms by IDF and
measuring coverage over the top 8 fixed it: 78 gaps, which matches the
dataset's own "known gaps" list.

**Boosts** come from columns the editorial pass already produced:

| signal | boost |
|---|---|
| destination match | +0.30 |
| destination mismatch | −0.22 |
| content-type match | +0.18 |
| intent match | +0.16 |
| priority: Core / Important / Low | +0.22 / +0.12 / −0.10 |
| AI support: strong / unclear | +0.15 / −0.12 |
| link behaviour: do not proactively link | −0.60 |

Destination mismatch is a strong negative because recommending a Fes page to
someone asking about Chefchaouen is the most visible way a link goes wrong.

Four further signals, each added after a specific failure:

**Title.** A page's title is the most reliable statement of what it covers,
more so than the content map's `content_type`, which is often wrong. Title
coverage of the question's key terms earns up to +0.55, tapering for long
questions, where rare words collide with titles by chance.

**Title topic.** Intents map to title vocabulary ("train", "riad", "day
trips"). Overlap between the question's topics and the title's earns a boost
proportional to how much of each is shared; a page whose title is clearly
about something else is penalised. This is what stops a train question
linking an AFCON hotels guide.

**Routes.** For "from X to Y" questions, a page covering only one end is a
different route, and a page without a transport topic in its title is not
about the journey.

**Subject beyond the place.** A page must match the question on something
other than its city to be linked. "Best steak place in Marrakech?" was once
linked to the Marrakech *flights* guide, carried over the threshold by
destination and editorial boosts alone. Country-wide pages need a clearer
match still, because half the site is "about Morocco". When the place *is* the
subject — "Chefchaouen?", "48 hours in Casablanca" — its own guide qualifies.

The gap detector applies the same rules, so a question that gets no link for
these reasons is also logged as a content gap.

---

## 4. Link selection

| complexity | links |
|---|---|
| simple | 0–1 |
| moderate | 0–2 |
| complex itinerary | 0–4 |

A link must clear 1.15; a *second* link must clear 1.45. One good link beats
two mediocre ones, and the style guide is explicit that not every answer needs
one.

Hard suppressions: pages marked "do not proactively link", destination
mismatch, near-duplicates of an already-chosen link, and anything already
linked earlier in the same conversation.

Anchor text comes from the content map's `Natural Anchor Text` column, with a
preference for the specific ("our Marrakech guide") over the generic ("our
Morocco guide").

---

## 5. Affiliate gating

Three gates, all of which must pass:

1. **Intent gate.** The traveller has to be arranging something. Commercial
   intent must be `high`, or an explicit booking phrase must be present.
   `medium` alone is not enough — that is what merely *mentioning* a tour
   produces, and "we already have a tour booked" must not be sold a tour.
2. **Advisory guard.** "Should I…", "do I need…", "is it worth…" are requests
   for advice. They return nothing, per the affiliate map's instruction to
   answer honestly first and show options only if the traveller comes back
   wanting them.
3. **Match gate.** Activities must match the destination. Activity categories
   are ranked by keyword specificity, because "desert tour from Marrakech"
   matches both `Desert Tour` and `Day Trip`, and returning a waterfall
   excursion to someone asking about the Sahara is exactly the failure the
   affiliate map warns about.

Blocked outright: off-topic, greetings, safety, visa, impossible actions, and
`PROBLEM` — someone whose flight was cancelled wants help, not a shopping
link.

Category suppression stops a specific match dragging in a broader one:
flight compensation silences flight search, luggage storage silences airport
transfer, attraction tickets silence general tours.

Disclosure is rendered by the interface, not left to the model to remember,
and every affiliate card carries `rel="sponsored nofollow"`.

---

## 6. Prompt architecture

Both spec documents say not to implement the personality as one giant prompt.
It is built in layers, and the layers that can be code are code:

| layer | where | per request? |
|---|---|---|
| identity, voice, hard rules | `prompts.py` constants | no |
| length and structure guidance | injected from classification | yes |
| retrieval context | injected from retriever | yes |
| trip context | injected from trip state | yes |
| **link selection** | `knowledge/links.py` | **not in the prompt** |
| **affiliate selection** | `knowledge/affiliates.py` | **not in the prompt** |

The model is told what will be rendered beneath its answer so the prose can
lead into it, and is explicitly told not to paste URLs or say "click here".

---

## 7. Trip state

A structured object, not just chat history. When someone says "actually, add
Essaouira", the assistant has to still know the trip is 12 days, two adults,
arriving in Casablanca.

Rules extract first (free, deterministic, testable), then the small model
refines and merges. Two behaviours matter most, and both come straight from
the multi-turn tests:

- `excluded_destinations` — a rejected suggestion never returns (MT-001,
  MT-005). An exclusion always outranks a want.
- `constraints` — "my phone is locked", "no climbing", "needs a car seat"
  survive every later turn and are injected into the prompt as hard
  constraints (MT-004, MT-001).

`already_visited` covers MT-010, where the traveller has been to Essaouira and
it must not be proposed as new.

---

## 8. Quality check

1. Regex scan — fabricated experience, claimed actions, sales pressure,
   inline URLs, brochure language. Free, runs always.
2. Model review — the judgement calls a regex cannot make, chiefly whether a
   stated constraint was ignored.

A major issue triggers one repair attempt. If the repair also fails the answer
is still sent — a flawed answer beats an error page — and the message is
flagged for `/api/admin/flagged`.

**Streaming caveat:** text is already on screen, so streamed answers get the
scan and the flag, not the repair. The non-streaming path used by the
evaluation does repair. This is the deliberate cost of a fast first token.

---

## 9. Data model

`Session` → `Conversation` → `Message` → `Feedback`, plus `Event`,
`ContentGap` and `UsageCounter`.

No accounts, no names, no emails. A session is an opaque id in localStorage.
IP addresses are stored only as a salted hash, only for rate limiting, and the
salt is the widget key so hashes are not portable between environments.

Negative feedback automatically opens a moderation item — that is the signal
the review queue is built around.

---

## 10. Cost and abuse

- Sliding-window rate limits, keyed on session **and** hashed IP, so one
  office behind one NAT is not one bucket.
- A daily token budget that fails closed.
- History capped at 12 turns.
- Messages capped at 2,000 characters; repeated-character floods rejected.
- Two models: the answer model for prose, a small model for classification,
  extraction and review.
- Prompt-injection attempts are logged and monitored rather than blocked,
  because blocking on those phrases would reject legitimate questions.

---

## 11. Decisions that need sign-off

**Live data is off.** No weather or schedule integration exists, so
`LIVE_DATA_ENABLED=false` and the assistant says plainly that it cannot check
current conditions. Turning the flag on without wiring a real tool would make
it claim otherwise. Phase 2 work.

**Only English and French are claimed.** Spanish, Arabic and Darija are
*detected* so someone writing in Arabic is not answered in English, but they
are not listed as supported and the linked content remains English.

**New pages are not recommended until reviewed.** Pages that appear in
WordPress but have never been classified are retrievable as context and marked
`needs_review`, but are not offered as recommendations. The alternative —
auto-classifying and recommending — risked pointing travellers at thin or
commercial pages nobody had judged.

**Affiliate maximum is two cards.** The specs give a range for links but not
for affiliates. Two was chosen to match the link ceiling for simple questions.

**Retention is 90 days.** The MVP scope asks for "a reasonable retention
policy" and defers the number to legal advice. 90 days is configurable via
`CONVERSATION_RETENTION_DAYS` and needs confirming before launch.

---

## 12. What is deliberately not built

Live APIs, user accounts, saved itineraries, maps, the browser extension, the
mobile app, social-answer mode, booking integration. All Phase 2+ in the
scope. The architecture leaves room for each — the tool layer, the
session/conversation split — without any of them blocking V1.
