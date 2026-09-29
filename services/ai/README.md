# ComeMorocco AI

A Morocco travel assistant for ComeMorocco.com. It answers travel questions
like a knowledgeable person rather than a brochure, and connects travellers to
ComeMorocco content and booking options when — and only when — that genuinely
helps.

Built to the specification in `01_PRODUCT_BRIEF.md`, `02_MVP_SCOPE.md`,
`03_AI_PERSONALITY.md` and `04_ANSWER_STYLE_GUIDE.md`, using the datasets in
`05_GOLDEN_QUESTIONS.xlsx`, `06_COMEMOROCCO_CONTENT_MAP.xlsx` and
`07_AFFILIATE_MAP.xlsx`.

---

## Quick start

Needs **Python 3.11 or newer**. On macOS the built-in `python3` is 3.9, which is
too old — install a current version from python.org first.

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
make build
make test
make run
```

Then put a key in `.env` and check it with one real request:

```bash
make check-model
```

Without a key, everything except the written answers still works: build,
tests, the offline evaluation, retrieval, link and affiliate selection, and
the widget.

## Choosing a model

Two providers are supported; the one whose key is in `.env` is used.

**Anthropic** (`ANTHROPIC_API_KEY`) is what the prompts were written and
evaluated against: a model strong enough to follow the full personality and
style specification.

**OpenRouter** (`OPENROUTER_API_KEY`) gives access to many models, including
free ones. The default is `nvidia/nemotron-3.5-lightning:free`. Three things to
know about it:

- **Request limits.** Free models allow 20 requests a minute, and 50 a day
  unless you have bought at least $10 of OpenRouter credit (then 1,000). Failed
  requests count too. On a `:free` model the service therefore makes **one**
  model call per question instead of up to four: classification and trip
  extraction fall back to the rule-based versions, and the model quality
  review is off. The regex scan for invented experiences, claimed bookings and
  sales pressure still runs on every answer.
- **It is a much smaller model** (3B active parameters of 30B). Expect
  answers that follow the voice and rules less closely than the specification
  intends. Good for development; judge it with `make eval-model` before
  putting it in front of travellers.
- **It is a reasoning model**, and does not support enforced JSON output. The
  service keeps reasoning short and out of the response, strips any `<think>`
  text that leaks into the answer — including mid-stream — and parses JSON
  loosely.

To use a paid OpenRouter model instead, set `OPENROUTER_MODEL` to its id; the
optional calls then switch back on.

Then open `widget/demo.html` to try the chat interface.

```bash
make test     # 115 tests, no API key needed
make eval     # offline evaluation over all 213 golden questions
```

---

## The one idea worth knowing

**Links and affiliate offers are chosen by code, before the model writes
anything.**

The model is told what will appear beneath its answer so it can lead into it
naturally. It does not choose. A model asked to "link when genuinely useful"
drifts toward linking always; a ranking function does not drift.

That is what makes *relevance before revenue* a property of the system rather
than a hope about prompt wording. `app/knowledge/links.py` and
`app/knowledge/affiliates.py` are where those decisions live, and
`tests/test_pipeline.py` asserts they hold across the whole golden set.

---

## How a question is answered

```
message
   ↓
language detection            app/core/language.py
   ↓
intent classification         app/core/intent.py       rules first, model refines
   ↓
trip state extraction         app/core/trip_state.py   runs concurrently
   ↓
safety check                  app/core/safety.py
   ↓
retrieval                     app/knowledge/index.py   BM25 + metadata boosts
   ↓
link selection                app/knowledge/links.py   budget, dedupe, suppression
   ↓
affiliate gating              app/knowledge/affiliates.py
   ↓
generation                    app/core/prompts.py + llm.py
   ↓
quality check                 app/core/quality.py      one repair attempt
   ↓
answer + resource cards + (maybe) one partner link
```

Classification and trip-state extraction run concurrently — they are
independent and both hit the small model, so running them in sequence would
add roughly 600ms to every response for nothing.

### Why retrieval is lexical, not vector

BM25 over the content map's own fields, with boosts from the columns the
editorial pass already produced: destination match, intent match, content
priority, AI-support rating. No embedding call.

For 240 pages this is not a compromise. It keeps retrieval off the latency
budget, makes the evaluation reproducible, and means the ranking is
explainable — every score decomposes into a lexical part, a coverage part and
named boosts, which is what makes the moderation queue useful. `HybridIndex`
can layer embeddings on later behind the same interface.

Scores separate cleanly on the real corpus:

| match quality | score |
|---|---|
| strong (the obvious page exists) | 1.3 – 2.1 |
| loose topical match | ~1.0 |
| nothing on the site covers it | ~0.4 |

`tests/test_pipeline.py::TestRetrieval` asserts that separation still holds,
because the link thresholds depend on it.

---

## What it refuses to do

These are enforced in code, not just requested in the prompt:

- **Never claims personal experience.** A regex scan plus a model review; a
  failure triggers one repair attempt, and a persistent failure is flagged for
  the moderation queue rather than shown as an error.
- **Never presents changeable information as checked.** `LIVE_DATA_ENABLED`
  is false because no weather or schedule integration exists yet. While it is
  false the prompt says so explicitly and the UI adds a notice.
- **Never sells on an informational question.** "What should I see in
  Marrakech?" returns no affiliate, by design. "Should I rent a car?" returns
  advice, not a rental site. Only "where can I rent a car?" opens the
  commercial path.
- **Never recommends a page that contradicts the question.** A destination
  mismatch is a hard suppression, because it is the most visible way a link
  recommendation goes wrong.
- **Never shows an unverified partner link.** Kiwi.com has no affiliate link in
  the source, only a widget, so it is marked unusable rather than having a URL
  invented for it.

---

## Evaluation

```bash
make eval                                   # offline, deterministic, runs in CI
python -m eval.harness --limit 30 --rubric  # with real answers and model grading
python -m eval.harness --multi-turn         # the 10 constraint-tracking tests
python -m eval.harness --compare eval/reports/eval-<previous>.json
```

Current offline results over all 213 golden questions:

| scorer | score |
|---|---|
| affiliate discipline | 0.958 |
| link discipline | 1.000 |
| retrieval | 0.378 |
| live-data detection | 0.638 |

77 of the 213 questions are ones ComeMorocco has **no page for**. Those are
recorded as editorial gaps, not scored as retrieval failures.

**The retrieval score is a weak signal and should not be tuned against.** It
compares words in the dataset's "content opportunity" column — which describes
the article ComeMorocco *should* write — with the titles actually linked. It
has rated a move from no link to a perfect bargaining guide as a failure, and
a move from the Merzouga page to a Marrakech city guide, for a Sahara
question, as a win.

Retrieval quality is guarded instead by `tests/test_retrieval_quality.py`: 20
hand-annotated cases, each listing acceptable first links and pages that must
never be linked. Most come from real regressions found while tuning, so the
same mistake cannot return unnoticed. Change retrieval, run it, and read a
random sample of what changed — the aggregate number alone is not enough.

Live-data detection at 63.8% is the honest weak spot. It has not been
over-fitted to the dataset; see *Known limitations*.

---

## The content-gap engine

Every question the assistant answers well but cannot support with a page is
logged, fingerprinted and counted. `GET /api/admin/content-gaps` returns them
ordered by frequency — an editorial brief list generated from what travellers
actually ask.

The current knowledge base flags 78 such gaps out of 213 golden questions,
which matches the "known gaps" list in the dataset's own README (private
driver day rates, tipping, Rabat and Meknes, train fares, accessibility).

---

## Layout

```
app/
  core/          language, intent, trip state, prompts, generation, quality, safety
  knowledge/     loader, BM25 index, retriever, link engine, affiliate engine
  api/           chat (SSE + JSON), feedback, analytics, admin
  db/            models and repository; SQLite by default, Postgres-ready
  infra/         rate limiting, logging
widget/          embeddable chat widget (Shadow DOM, no dependencies)
wordpress-plugin/  thin plugin: renders the widget, exports content
eval/            golden-question harness and scorers
scripts/         knowledge-base build, WordPress sync, affiliate map generator
data/source/     the original spreadsheets
data/knowledge/  generated runtime JSON
docs/            technical design, privacy, operations
```

---

## Deployment shape

```
comemorocco.com (WordPress)
   │  plugin renders the widget, exports content
   ▼
ai.comemorocco.com (this service)
   ├── rate limiting, token budget
   ├── orchestrator
   └── Postgres
```

The plugin holds no model key and no spend. It knows a service URL, a widget
key that is public by design, and a sync secret scoped to one endpoint. A
compromised WordPress install cannot read the moderation queue or run up an
API bill.

See `docs/OPERATIONS.md`.

---

## Known limitations

**Long forum-style questions get fewer links.** Relevance is partly measured
as the share of a question's distinctive words a page covers, and a 90-word
post covers more ground than any single page. The ranking for these is
generally right; the absolute link threshold is conservative, so some get no
link where a reasonable one exists (GQ-051, trouble booking Al Boraq, ranks two
train pages first but links neither). No link was preferred over tuning the
threshold for individual questions.

**Some links are still wrong.** A random read of changed links after the last
round of tuning found most better, and these still wrong:
- GQ-169, four days in Marrakech: the restaurants guide instead of *How Many
  Days in Marrakech*, which ranks fifth.
- GQ-027, a month in Marrakech or Agadir: *City Tours*, a thin listing page.
- GQ-213, transport sold out to Taghazout: a budget article.

**The content map's `content_type` column is unreliable.** The flights guide
is typed as a money guide, and an AFCON hotels page as transport. Retrieval
therefore reads a page's topic from its title and gives content type little
weight. Fixing the column would let it count for more.

**Live-data detection is 63.8% aligned with the dataset.** The dataset marks
prices, fares, tipping amounts and provider recommendations as time-sensitive;
the rules catch most but not all. The failure is one-directional by design —
the prompt tells the model it has no live sources regardless, so a miss means
a slightly less prominent caveat, not an invented schedule.

**One content map row is corrected at build time.** The blog index page
(`/blog/`) is labelled a Core weather guide with "Usually link", so it won
nearly every weather question. `scripts/build_knowledge_base.py` overrides it
and prints the correction on every build; fix it in the spreadsheet and delete
the entry from `DATA_CORRECTIONS`.

**The affiliate map needs two fixes before launch.** Both come from the source
data, and `data/source/07_AFFILIATE_MAP.xlsx` lists all 13 review items:
- Kiwi.com has no affiliate link, only a widget. Marked unusable.
- 12 `gyg.me` short links are shared across 25 different activities, so a
  traveller asking about Fes could be sent to an Agadir product. The engine
  de-duplicates by URL as a mitigation, but the links need verifying in the
  partner dashboard.

**Four widgets are preconfigured for the wrong place** — Hostelworld defaults
to New York, Klook to `city_id=289`, Viator to a fixed product, Localrent to
`country=99`. They are stored but not embedded anywhere yet.

**The quality check cannot repair a streamed answer.** Text is already on
screen. Streaming responses get the regex scan and are flagged for review;
the non-streaming path used by the evaluation does repair. That is the
deliberate trade for a fast first token.

**Newly published pages are not recommended until reviewed.** `wp_sync.py`
infers a classification for pages the content map has never seen and marks
them `needs_review`, with `link_behavior` set to "do not proactively link".
They are retrievable as context immediately but will not be offered as a
recommendation until someone classifies them.

---

## Next

Phase 2 in the brief: live weather, ONCF schedules, saved itineraries, user
accounts. The architecture leaves room for each — `LIVE_DATA_ENABLED` and the
tool layer, the session/conversation split in the schema — without any of them
blocking V1.
