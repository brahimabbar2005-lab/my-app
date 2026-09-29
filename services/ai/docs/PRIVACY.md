# Privacy and Data Handling

Implementation notes for `02_MVP_SCOPE.md` §31 and `01_PRODUCT_BRIEF.md` §18.

**This describes what the system does. It is not legal advice.** The scope
document says retention and consent must be finalised with legal advice before
launch; the open questions are listed at the end.

---

## What is collected

| Data | Why | Retention |
|---|---|---|
| Message text (traveller and assistant) | Answering, and quality review | 90 days |
| Anonymous session id | Continuity across page loads | 30 days after last use |
| Conversation trip state | So the traveller does not repeat themselves | With the conversation |
| Salted IP hash | Rate limiting only | With the session |
| User-agent family (truncated) | Debugging layout issues | With the session |
| Product events | Aggregate analytics | Indefinite, no message text |
| Feedback | Improving answers | With the message |
| Token counters | Cost control | Daily aggregate only |

## What is never collected

No names, emails, phone numbers, accounts, passwords, payment details,
precise location, advertising identifiers or cross-site tracking. No raw IP
address is written to the database or to logs.

The assistant does not ask for personal details, and nothing in the product
requires them. A traveller can use it without identifying themselves in any
way.

---

## Specific measures

**IP addresses.** Hashed with SHA-256 and a salt (the widget key), truncated
to 32 characters, used only as a rate-limit key. The raw address exists only
in the request object and is never persisted.

**Logs.** `app/infra/logging.py` allows an explicit field list — ids, timings,
counts, intents. Message text cannot reach the logs, because only allow-listed
fields are serialised.

**Storage in the browser.** One key, `cm_ai_session`, holding a random id. No
cookies are set by the widget. If storage is blocked the chat still works; the
session simply does not survive a page change.

**Consent.** The plugin can hold the widget back until the site's consent
banner signals acceptance (`respect_consent`, on by default), because
localStorage use may require consent in the EU. It listens for the common
banner events and exposes `window.ComeMoroccoAIConsent()` for custom banners.

**Retention.** `POST /api/admin/purge` deletes messages, conversations and
feedback past the window, and orphaned sessions past the session TTL.
Aggregate event counts survive; message text does not. Run it nightly:

```
0 3 * * * curl -sS -X POST https://ai.comemorocco.com/api/admin/purge \
  -H "X-Admin-Key: $ADMIN_KEY"
```

**Transport.** HTTPS everywhere. CORS is restricted to configured origins.

---

## Third parties

**The model provider** processes message text to generate answers. Which
one depends on configuration:

- **Anthropic** — under Anthropic's commercial terms, API inputs and outputs
  are not used to train models. A data processing agreement should be in
  place before launch.
- **OpenRouter** — requests are forwarded to whichever company hosts the
  chosen model, and data policies differ between hosts. Free endpoints in
  particular may log prompts or use them for training. Check the host's
  policy on the model's OpenRouter page, and OpenRouter's own privacy
  settings, **before real traveller conversations are sent through it**. A
  free model is fine for development with test questions; treat it as
  unsuitable for production until that has been checked.

**Affiliate partners** receive a visitor only when that visitor clicks a
partner link. No data is transmitted to them otherwise, and no partner script
runs inside the widget — the affiliate widget codes in the source data are
stored but not embedded. Every partner link is labelled and carries
`rel="sponsored nofollow"`.

---

## Rights requests

Data is anonymous, so ComeMorocco generally cannot link a conversation to a
person. If someone supplies their session id (visible in their browser's
localStorage), their conversations can be located and deleted.

Because the data cannot normally be tied to an identifiable person, most
subject-access obligations are limited in practice — but this is exactly the
point to confirm with a privacy adviser rather than assume.

---

## Open questions before launch

1. **Retention period.** 90 days is a default, not a decision. Confirm it.
2. **DPA with the model provider.** Needs signing with Anthropic, or — if
   OpenRouter is used in production — checking against the host's terms.
3. **Privacy policy.** Must be updated to cover AI chat, what is stored, and
   the Anthropic sub-processor relationship.
4. **Consent classification.** Is the session id strictly necessary
   (functional) or does it require consent? This determines whether
   `respect_consent` can be turned off.
5. **Affiliate disclosure wording.** The interface labels every partner link;
   the exact phrasing should be checked against the jurisdictions ComeMorocco
   serves.
6. **Terms of service.** Should state that AI answers can contain errors and
   that visas, health, transport and safety information must be verified — the
   scope document calls for this explicitly.
