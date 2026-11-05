# Keyword research → published post: workflow plan

This plan turns the method from the video into a repeatable pipeline for comemorocco.com. It follows the same steps as the video:
**keyword formats → APTK → autocomplete validation → ChatGPT query fan-outs → (optional) Ahrefs creative mode**,
then adds the steps we did by hand for the Agafay post: brief, draft, widgets, QA and a WordPress draft.

The rule the video repeats is *"AI guides the strategy, a human stays in the loop."* So the plan
automates the repetitive work: crawling, prompting, autocomplete scraping, checks and formatting.
It keeps a person at the five decision points: **pick the topic, pick the keyword, check the facts,
approve the images, press Publish.**

Reference run: the Agafay post (`posts/agafay-desert-marrakech.html`,
`aptk-agafay-keyword-research.md`). Every stage below is something we already did once by hand.

---

## 1. The pipeline at a glance

```
            ┌──────────────── automated ────────────────┐   ┌─ you ─┐
 A Topics   sitemap crawl → coverage index → APTK prompts 1+2 → gap check ──▶ [PICK TOPIC]
 B Keywords APTK prompt 3 → autocomplete (Google/Bing/DDG) → feedback prompt ──▶ [PICK KEYWORD + SERP look]
 C AEO      fan-out approximation via API  (+ your monthly manual check) ──▶ adds H2s/FAQs
 D Draft    brief → Claude writes in template → widgets → QA checks ──▶ [FACT-CHECK + EDIT]
            image prompts ──▶ [GENERATE/APPROVE IMAGES]
 E Publish  WordPress REST → DRAFT with Rank Math fields ──▶ [PREVIEW + PUBLISH]
 F Learn    Search Console after 4–8 weeks → new keyword ideas back into B
```

The **Google Sheet is the control panel**, as in the video ("Meta title / Keyword / Stage").
Each workflow reads a row, does its work, writes its results back, and sets a status. Your
decisions are made by changing a status cell. That status change is what starts the next workflow.

---

## 2. What's manual and what's automated

| # | Video step | Automated | Manual (you) | Why it stays manual |
|---|---|---|---|---|
| 0 | Set up the Claude project with APTK | Prompt stored once as the system prompt in every Claude call | Write and maintain the **site profile** (audience, products, affiliate list) | Only you know the business. The video calls this "the product marketing side" |
| 1 | Understand TOFU/MOFU/BOFU | Built into the APTK prompt and the sheet's `stage` column | — | — |
| 2a | Prompt 1: topics from audience × products | ✅ | — | — |
| 2b | Prompt 2: concise topic clusters | ✅ | — | — |
| 2c | Gap check against your own site | ✅ crawl `post-sitemap.xml`, match titles/H2/H3 (as we did for Agafay) | — | — |
| 2d | **Pick one topic** | Ranked shortlist with gap and affiliate-fit scores | **Choose one** | The video: "use your intuition… pick just one" |
| 2e | Prompt 3: keyword ideas per funnel stage | ✅ | — | — |
| 3a | Autocomplete validation | ✅ type-ahead simulation on Google + Bing + DuckDuckGo suggest (prefixes and `seed + a…z`) | Spot-check 1–2 seeds in incognito when results look odd | The endpoints are unofficial and can change or rate-limit |
| 3b | "It didn't autocomplete, but I found…" follow-up prompt | ✅ validated suggestions and the competitors you note are fed back to Claude | Add competitor names you saw in the results | — |
| 3c | **SERP check** (is the top result optimised for the exact keyword in its slug?) | Optional: SERP API counts exact-match slugs in the top 10 | **Look at the SERP and pick the primary keyword** | Judging search intent and competitor quality needs a human |
| 3d | Top vs middle suggestion (new vs established topic) | Flags whether the site already has ≥3 posts on the topic | — | — |
| 4 | ChatGPT query fan-out | Approximation: OpenAI Responses API with web search logs the searches it runs | **Monthly: the real DevTools → Network → `queries` check** on 2–3 prompts per cluster | ChatGPT's own fan-outs are only visible in a logged-in browser |
| 5 | Ahrefs/Semrush creative mode (optional) | Only if you buy API access: low-DR and modifier filters | Otherwise skip, or do it in the UI occasionally | Paid tool, and optional in the video |
| — | Brief and internal links | ✅ secondaries, fan-out questions, top 10 internal links ranked by relevance from the coverage index | — | — |
| — | Draft in the ComeMorocco template | ✅ Claude, with template rules (no H1, cm- blocks, `/affiliate-disclaimer/`) | — | — |
| — | Affiliate widgets | ✅ keyword → GYG `data-gyg-q` map + Travelpayouts links by context (camps→Booking, transfer→Kiwitaxi…) | Approve the mapping table once | — |
| — | QA checks | ✅ see §5 | — | — |
| — | **Fact-check and edit** | Flags every number, price and claim for review | **Check prices against the widgets, remove anything unverifiable, add local tips** | AI drafts can invent facts. Your local knowledge is the moat |
| — | Images | ✅ prompts and alt text generated | **Generate, choose and upload** | Quality and honesty (no fake "real camp" photos) |
| — | **Publish** | ✅ creates a WordPress **draft** with title, slug, excerpt, category and Rank Math fields | **Preview and press Publish** | Never auto-publish to a live, monetised site |
| — | Rinse and repeat | ✅ GSC queries at 4–8 weeks → new rows in the Keywords tab | Decide whether to update the post or write a new one | — |

**Your time per post:** about 45–75 minutes (pick the topic, pick the keyword, fact-check and edit, images, publish).
Everything else runs unattended.

---

## 3. The control sheet (Google Sheets)

One spreadsheet, four tabs.

**`Profile`** (you edit this): audience personas, products/offers, affiliate programs + IDs,
GYG partner ID `7BARAIK`, banned claims, tone notes.

**`Topics`**: `topic | cluster | funnel_fit | existing_posts | gap_score | affiliate_fit | status`
`status`: `new → selected | rejected`

**`Keywords`**: `topic | keyword | stage (TOFU/MOFU/BOFU) | source (claude/autocomplete/gsc/fanout) |
google_ac | bing_ac | ddg_ac | ac_position | serp_exact_slugs | notes | status`
`status`: `idea → validated | not_found → primary | secondary | rejected`

**`Posts`**: `primary_keyword | secondaries | meta_title | slug | meta_description | excerpt |
category | brief_url | draft_path | qa_result | wp_draft_id | status | published_url | published_at`
`status`: `brief → drafted → qa_failed | ready_for_review → approved → wp_draft → published`

The video's three columns (meta title, keyword, stage) are in there. The rest is what automation needs.

---

## 4. The workflows (n8n)

n8n is already connected to this workspace (MCP), so it's the recommended engine. Make would also work.
Claude calls use the Anthropic API with the APTK prompt as the system prompt.

### A — Topic discovery · *monthly schedule, or manual trigger*
1. Fetch `post-sitemap.xml` and `page-sitemap.xml` → each URL's `<title>`, H2 and H3 → **coverage index**
   (an n8n Data Table). Headings only, because nav and footer text inflate counts (we found this on the Agafay run).
2. Claude, **APTK prompt 1** with the site profile → topic list.
3. Claude, **APTK prompt 2** → concise 2–5 word clusters.
4. Score each cluster: how many existing posts cover it as a **main topic** vs only a subsection,
   whether a bookable product exists (GYG / Booking / transfer), and funnel stage.
5. Write the rows to `Topics` with `status = new`, and notify you (email/Slack).
6. 🧑 **You set one row to `selected`.**

### B — Keyword ideas + validation · *triggered by a topic → `selected`*
1. Claude, **APTK prompt 3** for that topic → TOFU/MOFU/BOFU keyword ideas.
2. For each idea, simulate typing, as in the video: query the suggest endpoint with progressively longer
   prefixes (`best no co…`, `best no code…`), plus `seed + a…z` and `seed + space`.
   - Google: `suggestqueries.google.com/complete/search?client=firefox&q=…`
   - Bing: `api.bing.com/osjson.aspx?query=…`
   - DuckDuckGo: `duckduckgo.com/ac/?q=…`
   Throttle to about 1 request per second, cache results for 7 days, and set `hl=en&gl=us` (your main market). A second pass with `gl=gb` is optional.
3. Mark each idea `validated` if it appears in the suggestions, otherwise `not_found`. Store `ac_position`.
   Add the **new suggestions found along the way** as rows with `source = autocomplete`. That's how
   "agafay desert tour" (not found) turned into "agafay desert camp / quad / marrakech" (found).
4. **Feedback prompt** (video at about 25:00): send Claude the not-found ideas, the validated finds and
   any competitors in `notes` → ask for more BOFU ideas (comparisons, alternatives, "best X") → run them through step 2 again, **once**.
5. Optional: a SERP API (Serper, DataForSEO…) fetches the top 10 for each validated BOFU/MOFU keyword
   → `serp_exact_slugs` = how many results have the exact keyword in the URL slug (the video's test).
6. Suggest a primary keyword: a validated one from the **middle** of the suggestion list if the site has fewer than 3
   posts on the topic, otherwise the top one (video at about 23:10).
7. Notify you. 🧑 **You look at the SERP and set one row to `primary`, plus a few `secondary` rows.**

### C — AEO / query fan-out · *triggered with B's output, optional*
1. Turn the primary and secondary keywords into 3 natural prompts ("What are the best… ?").
2. Send each to the **OpenAI Responses API with the web search tool enabled**. Its output includes the
   search queries the model ran. Log them as `source = fanout`.
   This approximates ChatGPT, it isn't ChatGPT itself, so treat it as idea generation.
3. Recurring patterns that aren't covered (e.g. "how to … without …") → candidate H2s and FAQ questions in the brief.
4. 🧑 **Monthly, 15 minutes:** do the real DevTools check from the video on 2–3 prompts per active cluster
   and paste the `queries` into the sheet. That keeps the approximation honest.

### D — Brief + draft · *triggered by a keyword → `primary`*
1. **Brief** (JSON + a readable doc): primary/secondaries, funnel stage, search-intent summary,
   fan-out questions, the 8–12 most relevant internal links from the coverage index (all checked to return 200),
   the affiliate placements from the mapping table, and things that must not be invented (prices, quotes, named businesses).
2. **Draft**: Claude writes the post as HTML in `post-template.html`, following the template's rules.
   The prompt includes the Agafay post as a style example.
3. **Widgets**: insert the GYG blocks (`data-gyg-q` from the mapping, "Powered by" link to a real GYG
   category page) and Travelpayouts links with `rel="sponsored noopener"`.
4. **Image prompts + alt text** for each `<figure>` and the featured image.
5. Save to the repo (`docs/content/posts/<slug>.html`) or Drive → run the QA checks (§5).
   Pass → `ready_for_review`. Fail → `qa_failed`, with the reasons.
6. 🧑 **You fact-check and edit**, generate the images (Canva is connected) and upload them, then set `approved`.

### E — Publish as draft · *triggered by `approved`*
1. WordPress REST `POST /wp-json/wp/v2/posts` with **status `draft`**, title, slug, excerpt,
   category, featured image ID and content.
2. Set the Rank Math focus keyword, meta title and meta description. Rank Math's meta keys aren't exposed
   to the REST API by default, so this needs a small `register_post_meta(... 'show_in_rest' => true)`
   snippet. The repo's `services/ai/wordpress-plugin` could host it.
3. Write `wp_draft_id` and the preview link to the sheet and notify you.
4. 🧑 **You preview it on the real theme (widgets render there) and press Publish.**

### F — Learn · *weekly schedule*
1. Search Console API: for posts 4–8 weeks old, list the queries with impressions where position is 8–30.
2. New queries go into `Keywords` with `source = gsc`. Queries that fit an existing post become "update post" tasks.
3. Watch for cannibalisation (two of your URLs ranking for the same query) and flag it.

---

## 5. Automated QA checks (run on every draft)

All of these were done by hand on the Agafay post:

- Exactly 0 `<h1>`. H2/H3 only.
- Every `href="#…"` in the contents block has a matching `id`.
- HTML is balanced (parser check).
- Every internal link returns 200 (live fetch).
- Disclosure links to `/affiliate-disclaimer/` (the template's `/affiliate-disclosure/` is a 404).
- Every external partner link has `rel="sponsored…"`.
- GYG blocks use partner `7BARAIK`, locale `en-US`, items `1`.
- The primary keyword appears in the first 100 words and in at least one H2.
- No leftover `[…]` placeholders except `[IMAGE URL]`.
- No `<script>` except the approved Travelpayouts embeds.
- **Fact flags:** every number, € or $ amount, and named business is listed for your review (never auto-approved).
- Word count within the target for the funnel stage (BOFU guide about 1,500–2,500).
- No blockquote unless a source is given (no invented quotes).

---

## 6. What you need to set up once

| Item | Used by | Notes |
|---|---|---|
| n8n instance (already connected) | All | Workflows A–F |
| Google Sheet + Google credential in n8n | All | Control panel |
| Anthropic API key | A, B, D | APTK prompt as the system prompt |
| OpenAI API key | C (optional) | Fan-out approximation |
| SERP API key | B step 5 (optional) | About $50/month at most for this volume |
| WordPress **Application Password** for an Editor user | E | WP Admin → Users → Profile. Drafts only |
| Rank Math REST meta snippet | E | Small plugin or functions.php |
| Search Console access | F | Service account added as a user |
| Affiliate mapping table | D | Starts from the list you gave (GYG, Booking, Kiwitaxi, Welcome Pickups, Airalo…) |

Keep every key in n8n's credential store, never in this repo (`docs/MASTER_PLAN.md` §324 says the same).

---

## 7. Build order

1. **Week 1: control sheet + Workflow A + B.** This is where most of the value is. Test it on a topic we
   already know: *hot air balloon Marrakech* (the next gap from the Agafay research).
2. **Week 2: Workflow D** (brief → draft → QA), with the Agafay post as the regression example: re-running
   it on "agafay desert marrakech" should produce something close to what we shipped.
3. **Week 3: Workflow E** (WordPress drafts) once the application password and Rank Math snippet are in place.
4. **Later: C and F.** They need a few published posts before they're useful.

## 8. Risks and guardrails

- **Autocomplete endpoints are unofficial.** Keep the volume low, cache results, and fall back to manual if they start failing.
- **No fabricated data**, which is APTK rule 4: the pipeline never writes search volumes, difficulty scores or prices as fact.
  Prices go in only from a source you've confirmed.
- **No auto-publishing.** The pipeline stops at a WordPress draft.
- **Topical depth over volume.** Finish a cluster (e.g. Agafay: camps roundup → balloon → quad comparison)
  before starting a new one. That's the core of the video's strategy.
