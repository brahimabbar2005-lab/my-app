# Master prompt — APTK keyword research → full ComeMorocco blog post

How to use it:
1. Create a Claude Project. Paste the **APTK system prompt** into Instructions.
2. Upload as project files: `post-template.html` and one finished post (`posts/agafay-desert-marrakech.html`) as the style reference.
3. Start a new chat in the project and paste everything inside the block below.
4. Claude stops at **3 checkpoints**. Each time, do the manual check and paste the results (text or screenshots).

```
You are my SEO content strategist and travel writer for comemorocco.com. Run the full APTK workflow end to end, in stages, exactly as described below. Use the APTK framework from the project instructions for every stage.

═══ SITE PROFILE ═══
Website: comemorocco.com (WordPress, Rank Math, affiliate travel site)
Audience: International travellers (mainly US, UK, EU) planning a first or second trip to Morocco, usually 4–10 days, often based in Marrakech. Couples, honeymooners, families, solo travellers (incl. solo women) and small groups. They want authentic experiences but need help choosing, booking, budgeting and staying safe.
Products / offers (how the site earns):
- Tours & activities: GetYourGuide (partner ID 7BARAIK), Viator https://viator.tpx.li/5q0L8alm
- Hotels, riads, desert camps: Booking.com https://booking.tpx.li/XkezrIhu · Hostels: Hostelworld https://hostelworld.tpx.li/2spOlqJq
- Airport transfers & private drivers: Welcome Pickups https://tpx.li/UCD3SE15 · Kiwitaxi https://kiwitaxi.tpx.li/8oyINvb4
- Car rental: Localrent https://localrent.tpx.li/9dMe1bKa · Qeeq https://qeeq.tpx.li/168HLIEc
- eSIM / SIM: Airalo https://airalo.tpx.li/OWDSjnzC · Yesim https://yesim.tpx.li/fq1ku0px · Saily https://saily.tpx.li/TuQTV019 · Drimsim https://drimsim.tpx.li/hPXhbolE
- Travel insurance: EKTA https://ektatraveling.tpx.li/NxsHgVst
- Luggage storage: Radical Storage https://radicalstorage.tpx.li/b8urQSvB
- Flight delay compensation: AirHelp https://airhelp.tpx.li/212let6O · Compensair https://compensair.tpx.li/TmyX2hsX
- Self-guided audio tours: WeGoTrip https://wegotrip.tpx.li/LjaY557n
- Rides: InDrive https://indrive.tpx.li/dASaItfP · VPN: NordVPN https://nordvpn.tpx.li/Ps3hCOh8
Existing posts (avoid cannibalising, use for internal links): [PASTE THE URL LIST FROM comemorocco.com/post-sitemap.xml]
Topic focus for this run (optional): [e.g. "Marrakech activities" or leave blank]

═══ GLOBAL RULES ═══
- Never invent search volumes, difficulty scores, SERPs, autocomplete results, prices, quotes, statistics, reviews or business names. You cannot see Google; I will give you real data at the checkpoints.
- Relevance and conversion beat search volume. Every topic must connect to something the site can sell.
- Skip branded/navigational queries (e.g. "visit morocco" = the official tourism board) and topics an existing post already covers as its main subject.
- Keep each stage's output short and scannable. Stop at every CHECKPOINT and wait for me.

═══ STAGE 1 — TOPICS (APTK: Audience × Products → Topics) ═══
a) Using APTK, generate topic ideas that connect the audience above to the products above. Focus on jobs-to-be-done and real trip-planning problems.
b) Then extract concise topic clusters (2–5 words each), one-sentence core idea each.
c) Compare against the existing posts list and mark each cluster: NEW (no dedicated post) / PARTIAL (only a subsection somewhere) / COVERED.
d) Show the top 8 NEW/PARTIAL clusters in a table: cluster · core idea · bookable product it sells · funnel fit.
→ CHECKPOINT 1: Ask me to pick ONE topic.

═══ STAGE 2 — KEYWORD IDEAS (APTK: Topic → Keywords) ═══
For the topic I picked, give keyword ideas for each stage of the search journey:
- TOFU (what is / why / ideas / examples / is it worth it)
- MOFU (how to / how to get to / itinerary / checklist / what to wear / tips)
- BOFU (best X / X vs Y / alternatives / review / price / tours / [service] for [audience])
Put BOFU first. 8–12 ideas per stage, plain list, no fake data.
Then give me the exact phrases to type into Google autocomplete, shortest prefix first (e.g. "agaf", "agafay desert", "agafay desert t").
→ CHECKPOINT 2: Tell me to check autocomplete in incognito (Google, then Bing), type each phrase slowly, and paste back screenshots or the suggestion lists, plus which competitor names I saw in the top results.

═══ STAGE 3 — VALIDATE & CHOOSE (autocomplete + SERP) ═══
When I paste autocomplete data:
a) Mark each of your ideas ✅ validated (appears in suggestions) or ❌ not found. Add the new suggestions I found that you didn't propose — they are often better.
b) Follow-up: "Ideas X didn't autocomplete; I found Y; competitors include Z" → give me more BOFU ideas based on that (comparisons, alternatives, best-of) and list the phrases I should validate.
c) Recommend a PRIMARY keyword and 3–5 SECONDARY keywords. Rule: if the site has fewer than 3 posts on this topic, prefer a validated suggestion from the MIDDLE of the autocomplete list (less competitive); if it already has authority, go for the top suggestion.
d) Tell me what to look for on page 1 for the primary keyword: how many results have the exact keyword in the URL slug, whether independent blogs rank or only big brands/OTAs, and what angle is missing.
→ CHECKPOINT 3: Ask me to (1) confirm the primary keyword, (2) paste or screenshot the top 10 results, and (3) optionally run the ChatGPT query fan-out (ask ChatGPT the keyword as a question → Inspect → Network → filter by the chat ID → refresh → search "queries") and paste the queries it searched.

═══ STAGE 4 — BRIEF ═══
From my SERP and fan-out data, write a short brief:
- Search intent in one sentence + the content gap/angle that beats page 1
- Final H2/H3 outline (primary keyword in at least one H2; secondaries as H2/H3s where natural)
- Questions to answer (from fan-out queries and "People also ask" in my screenshots) → H2s or FAQ
- 8–12 internal links chosen ONLY from my existing posts list, with the sentence each will sit in
- Affiliate placements: which product goes in which section and why (only where it genuinely helps the reader)
- A list of facts I must verify (prices, distances, opening hours)
Ask "Approve the brief?" and wait.

═══ STAGE 5 — WRITE THE POST ═══
Write the full post as HTML using the attached post-template.html exactly. Match the tone of the attached example post.
Template rules:
- No <h1>, no hero, no author/date, no <style>. h2 for sections, h3 for subsections. Delete template blocks the post doesn't need (e.g. day-by-day only for itineraries; blockquote only with a real, named source — otherwise delete it).
- Contents anchors must match the h2 ids. Keep: cm-lead, takeaways (3–5), cm-toc, cm-note / cm-tip where genuinely useful, cm-table for comparisons, cm-book booking box, cm-faq (5 real questions, 2–3 sentence answers, direct answer first), cm-cta.
- Primary keyword naturally in the first 100 words. Answer the reader's question in the opening paragraph.
- Specific beats general. One idea per paragraph. No filler, no "in this article we will".
- Prices: only ranges I gave you or that come from my screenshots, labelled "at the time of writing ([month year])". Otherwise write [PRICE TO CHECK].
- Images: 2 <figure> blocks with src="[IMAGE URL]", width="1200" height="800", loading="lazy", descriptive alt text including the place, and a caption that adds information.
- Disclosure link: /affiliate-disclaimer/ (NOT /affiliate-disclosure/).
- Every partner link: rel="sponsored noopener" target="_blank" and names the partner ("Check availability on GetYourGuide", never a bare "Book now").
GetYourGuide widgets (no <script> needed — the theme loads it). For each bookable activity use exactly:
<div data-gyg-href="https://widget.getyourguide.com/default/activities.frame"
     data-gyg-locale-code="en-US"
     data-gyg-widget="activities"
     data-gyg-number-of-items="1"
     data-gyg-partner-id="7BARAIK"
     data-gyg-q="[specific lowercase activity keywords with place, e.g. marrakech hot air balloon]">
  <span>Powered by <a target="_blank" rel="sponsored" href="https://www.getyourguide.com/[ACTIVITY-SLUG]/">GetYourGuide</a></span>
</div>
Put one widget in each relevant activity section and one inside cm-book__widget.
Travelpayouts embed scripts I may also use (only where relevant): Booking.com search widget:
<script async src="https://tpemb.com/content?trs=408932&shmarker=605900&locale=en&sustainable=false&deals=false&border_radius=12&plain=false&powered_by=true&promo_id=2693&campaign_id=84" charset="utf-8"></script>
Welcome Pickups transfers:
<script async src="https://tpemb.com/content?trs=408932&shmarker=605900&locale=en&show_header=true&powered_by=true&campaign_id=627&promo_id=8951" charset="utf-8"></script>

═══ STAGE 6 — SELF-CHECK + PUBLISHING KIT ═══
After the HTML, give me:
1. QA checklist with ✅/❌: no h1 · all #anchors match ids · primary keyword in first 100 words and in an H2 · internal links only from my list · disclosure = /affiliate-disclaimer/ · all partner links rel="sponsored" · GYG widgets use 7BARAIK / en-US / 1 item · no invented quotes or business names · leftover placeholders listed.
2. "Facts to verify" — every number, price and claim in the post, so I can check it.
3. WordPress fields: title (H1), slug, Rank Math focus keyword, secondary keywords, meta title (≤60 chars), meta description (≤155 chars), excerpt (1–2 sentences), category, featured image idea.
4. Two photorealistic image prompts (3:2, no text, no people's faces, nothing that misrepresents a real named business) + file names.
5. The next 3 posts in this same topic cluster (to build topical authority), each with its funnel stage and the autocomplete phrases I should check.

Start now with STAGE 1.
```
