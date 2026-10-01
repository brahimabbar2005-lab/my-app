# APTK keyword research — Agafay Desert tours

The research behind `posts/agafay-desert-marrakech.html`. It follows the
five-step method: keyword formats → APTK → autocomplete validation → ChatGPT query
fan-outs → (optional) creative mode in Ahrefs/Semrush.

Researched 1 October 2026.

---

## 1. Audience

| Persona | Situation | What they search |
|---|---|---|
| First-time Morocco visitor (US/UK/EU), 3–5 nights in Marrakech | Wants "the desert" but has no room for the 3-day Merzouga trip | "desert near Marrakech", "is Agafay worth it", "Agafay or Merzouga" |
| Couple / honeymooners | Want one memorable evening: sunset, dinner, stars | "Agafay desert dinner", "Agafay sunset", "luxury camp Agafay" |
| Families with kids | Need short drives and safe activities | "Agafay with kids", "camel ride Marrakech kids" |
| Active travellers / groups of friends | Want adrenaline on a short trip | "quad biking Marrakech", "buggy Agafay" |

**JTBD:** "Give me a real desert experience without giving up two days of my trip to drive there."

## 2. Products / offers

ComeMorocco earns from affiliate tour bookings (GetYourGuide/Viator-style widgets), plus hotels, transfers and insurance.
The Agafay offers that are actually bookable:

- Sunset camel ride + dinner show (cheapest and the most booked)
- Quad bike / buggy sessions, alone or with dinner
- Full-day private 4x4 tour (Berber village, lunch, Lalla Takerkoust lake)
- Overnight camp stays (mid-range to luxury)

## 3. Topic gap (from the site's own sitemap)

I pulled all ~200 posts from `post-sitemap.xml` and checked their titles and H2/H3s.

- **Agafay**: only appears as a sub-section (in `/sahara-desert-tours-morocco-guide/`,
  `/marrakech-tours-desert-adventures-guide/`, `/where-to-stay-in-marrakech-2/`,
  `/marrakech-morocco-2026-travel-guide/`). **No dedicated page.**
- **Hot air balloon Marrakech**: also only a sub-section. → Next candidate.
- **Quad biking Marrakech**: sub-sections only. → Covered partly by this post, and could become its own page later.
- The Sahara/Merzouga cluster already exists (`/sahara-desert-tours-morocco/`,
  `/best-sahara-desert-tour-from-marrakech-2026-guide/`, `/desert-tour-marrakech-guide/`)
  → Agafay completes the desert cluster and links into it (topical depth).

Chosen topic: **Agafay Desert (bookable experiences from Marrakech)**.

## 4. Keywords by funnel stage

### Google autocomplete results (checked by the site owner, 1 Oct 2026)

`agaf…` → agafay luxury camp · agafay desert · agafay marrakech · agafay valley ·
agafay desert luxury camp · agafay valley camp · agafay quad

`agafay desert…` → agafay desert luxury camp · agafay desert hotel · agafay desert camp ·
agafay desert marrakech · agafay desert quad · *(business listing: "AGAFAY DESERT: Dinner, Camel Ride, Berber…")* ·
agafay desert camp marrakech

**What the check changed (step 3 of the method):** Claude's idea, *"agafay desert tour from marrakech"*,
**did not autocomplete**. As in the video's "best no-code prototyping tools" example, the check
turned up better keywords: searchers say **camp**, **luxury camp**, **hotel**, **marrakech** and **quad**.
The post was re-angled around those keywords.

| Stage | Keyword | Autocomplete | Where it's used |
|---|---|---|---|
| BOFU/MOFU | **agafay desert marrakech** (focus) | ✅ | Title, slug, H1, intro, getting-there section |
| BOFU | agafay desert camp / agafay desert camp marrakech | ✅ | H2 "Agafay desert camps" + Booking.com |
| BOFU | agafay luxury camp / agafay desert luxury camp | ✅ (top suggestion) | H3 tier. **Deserves its own roundup post** (see 7) |
| BOFU | agafay desert quad / agafay quad | ✅ | H2 "Agafay desert quad and buggy tours" + GYG widget |
| BOFU | agafay desert dinner (camel ride) | ✅ (a business named for it) | H2 "sunset camel ride and dinner" + GYG widget |
| TOFU | agafay valley | ✅ | Explained in "what it is" section |
| BOFU | agafay desert hotel | ✅ | Covered by the camps section. Later: a hotel/camp roundup |
| MOFU | agafay vs merzouga | SERP ✅ (crowded) | H3 only |
| BOFU | agafay desert tour from marrakech | ❌ not in autocomplete | Dropped as the focus keyword |

Per the video: for a topic that is new to the site, target a suggestion from the **middle of the list**
(*agafay desert marrakech*), not the top one (*agafay luxury camp*), which is the most competitive.
Once this post builds topical authority, go after the top suggestion.

## 5. Affiliate placement

- GetYourGuide widgets (partner 7BARAIK): `agafay desert quad biking`, `agafay desert dinner camel ride sunset`,
  `agafay desert marrakech` (booking box). "Powered by" links use real GYG pages:
  `/agafay-desert-l166143/`, `/agafay-desert-l166143/sunset-tours-tc306/`, `/marrakesh-l208/quad-atv-tours-tc38/`.
- Booking.com (Travelpayouts) link and search widget in the camps section.
- Kiwitaxi link in "Getting there".
- Every partner link has `rel="sponsored noopener"`, and the disclosure links to `/affiliate-disclaimer/`
  (the template's `/affiliate-disclosure/` returns 404, so fix it in the template too).

## 6. ChatGPT query fan-out check (step 4 — for you to run)

Prompts to run in ChatGPT (with search on), then Inspect → Network → filter by the
conversation ID → search `queries`:

- "What are the best camps in the Agafay desert near Marrakech?"
- "Is a night in the Agafay desert worth it?"
- "Best quad biking in Agafay desert"

Paste me the `queries` lists. Any recurring query the post doesn't answer becomes a new H2 or a new post.

## 7. Next posts in this cluster (in priority order)

1. **Best luxury camps in Agafay** — top autocomplete suggestion. BOFU roundup with Booking.com. Needs real camp research (names, prices, reviews)
2. **Hot air balloon Marrakech** — prices, what's included, is it worth it (BOFU, high ticket)
3. **Quad biking in Marrakech: Agafay vs Palmeraie** (BOFU comparison)
4. **Agafay Desert with kids** (MOFU, links to `/marrakech-with-kids-family-guide/`)

## WordPress fields for this post

- **Title (H1):** Agafay Desert, Marrakech: Camps, Quad Bikes and Sunset Dinners (2026)
- **Slug:** `agafay-desert-marrakech`
- **Rank Math focus keyword:** agafay desert marrakech
- **Secondary keywords:** agafay desert camp, agafay desert quad, agafay luxury camp, agafay valley
- **Meta title (≤60):** Agafay Desert Marrakech: Camps, Quads & Dinners (2026)
- **Meta description (≤155):** Marrakech's own desert is under an hour away. Agafay desert camps, quad tours and sunset dinners compared, with prices and how to get there.
- **Excerpt:** Under an hour from the medina, Agafay is Marrakech's stone desert. Here is how its camps, quad tours and sunset dinners compare, and which one fits your trip.
- **Category:** Desert / Marrakech
- **Featured image:** wide shot of Agafay's stony hills at sunset with the Atlas behind
