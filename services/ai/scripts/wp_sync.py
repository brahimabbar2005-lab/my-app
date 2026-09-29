#!/usr/bin/env python3
"""Pull published content from WordPress into the AI knowledge base.

    python scripts/wp_sync.py                 sync everything, then reindex
    python scripts/wp_sync.py --since 7       only pages changed in 7 days
    python scripts/wp_sync.py --dry-run       show what would change

Run it nightly from cron. The plugin also pings /api/admin/content-changed on
publish, which reindexes what is already on disk; this script is what actually
refreshes that disk copy.

The classification columns in 06_COMEMOROCCO_CONTENT_MAP.xlsx — when to
recommend a page, when not to, which traveller intents it serves — were
produced by an editorial pass, not by WordPress. So this script **merges**:
live fields (title, URL, excerpt, SEO text, freshness) come from WordPress,
and the editorial fields are preserved for pages already in the map.

A brand-new page therefore arrives with inferred classification and a
`needs_review` flag rather than silently entering the map as though a human
had judged it. Pages deleted in WordPress are removed, which is the failure
that matters most: recommending a page that 404s.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit("httpx is required:  pip install httpx")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.knowledge.index import tokenise  # noqa: E402

KNOWLEDGE = ROOT / "data" / "knowledge" / "content.json"

# Editorial judgement that WordPress does not know about and must not
# overwrite. These are carried forward for any page already in the map.
EDITORIAL_FIELDS = (
    "content_type", "primary_destination", "related_destinations", "primary_topic",
    "subtopics", "traveler_intents", "traveler_types", "related_questions",
    "when_to_recommend", "when_not_to_recommend", "anchor_texts", "priority",
    "affiliate_relevant", "affiliate_type", "time_sensitivity", "live_data_required",
    "ai_content_support", "link_behavior", "related_ids",
)

# Weak inference for pages that have never been classified. Deliberately
# conservative: a new page defaults to not being proactively linked until
# someone has looked at it.
DESTINATION_HINTS = {
    "Marrakech": ("marrakech", "marrakesh"),
    "Fes": ("fes", "fez"),
    "Chefchaouen": ("chefchaouen", "chaouen"),
    "Casablanca": ("casablanca",),
    "Rabat": ("rabat",),
    "Tangier": ("tangier", "tanger"),
    "Essaouira": ("essaouira",),
    "Merzouga": ("merzouga", "erg chebbi"),
    "Agadir": ("agadir", "taghazout"),
    "Sahara Desert": ("sahara", "desert", "erg chigaga"),
    "Atlas Mountains": ("atlas", "toubkal", "imlil", "ourika"),
    "Ouarzazate": ("ouarzazate", "ait benhaddou"),
    "Dakhla": ("dakhla",),
}

TYPE_HINTS = (
    ("Transportation Guide", ("train", "bus", "taxi", "transport", "getting around", "car rental", "driving")),
    ("Hotel / Accommodation Guide", ("hotel", "riad", "hostel", "where to stay", "accommodation")),
    ("Itinerary", ("itinerary", "days in", "day trip", "route")),
    ("Activity Guide", ("things to do", "tour", "activities", "experience", "cooking class", "hammam")),
    ("Food Guide", ("food", "eat", "restaurant", "cuisine", "tagine")),
    ("Weather / Seasons Guide", ("weather", "season", "in january", "in july", "best time")),
    ("Money / Budget Guide", ("budget", "cost", "money", "price", "cheap", "how much")),
    ("Safety Guide", ("safe", "safety", "scam")),
    ("Packing Guide", ("pack", "what to wear", "clothing")),
    ("Destination Guide", ("guide", "travel guide", "visit")),
)


def infer(title: str, text: str) -> dict[str, Any]:
    """Best-effort classification for a page nobody has reviewed yet."""
    haystack = f"{title} {text}".lower()

    destinations = [name for name, aliases in DESTINATION_HINTS.items()
                    if any(alias in haystack for alias in aliases)]
    content_type = next((name for name, words in TYPE_HINTS if any(w in haystack for w in words)), "Other")

    primary = destinations[0] if destinations else "Morocco"
    return {
        "content_type": content_type,
        "primary_destination": primary,
        "related_destinations": destinations[1:],
        "primary_topic": None,
        "subtopics": [],
        "traveler_intents": [],
        "traveler_types": ["General traveler"],
        "related_questions": [],
        "when_to_recommend": None,
        "when_not_to_recommend": None,
        "anchor_texts": [f"our {primary} guide"],
        "related_ids": [],
        "priority": "Standard",
        "affiliate_relevant": "No",
        "affiliate_type": None,
        "time_sensitivity": "Medium",
        "live_data_required": "No",
        "ai_content_support": "Unclear",
        # The important default: a page nobody has reviewed is retrievable as
        # context but is not offered to travellers as a recommendation.
        "link_behavior": "Do not proactively link",
        "needs_review": True,
    }


def fetch_all(base_url: str, secret: str, since: str | None, timeout: float) -> list[dict[str, Any]]:
    endpoint = f"{base_url.rstrip('/')}/wp-json/comemorocco-ai/v1/content"
    headers = {"X-Sync-Secret": secret}
    items: list[dict[str, Any]] = []
    page = 1

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        while True:
            params: dict[str, Any] = {"page": page, "per_page": 50}
            if since:
                params["since"] = since
            response = client.get(endpoint, params=params, headers=headers)
            if response.status_code == 401:
                sys.exit("WordPress rejected the sync secret. Check the plugin settings page.")
            response.raise_for_status()
            payload = response.json()
            items.extend(payload.get("items", []))
            total_pages = payload.get("total_pages", 1)
            print(f"  fetched page {page}/{total_pages} ({len(items)} items so far)")
            if page >= total_pages:
                break
            page += 1
    return items


def merge(existing: dict[str, Any], incoming: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Combine live WordPress fields with preserved editorial classification."""
    content_id = str(incoming["id"])
    previous = existing.get(content_id)

    def text(value: Any) -> str:
        return html.unescape(str(value or "")).strip()

    record: dict[str, Any] = {
        "id": content_id,
        "title": text(incoming.get("title")),
        "url": incoming.get("url") or "",
        "excerpt": text(incoming.get("excerpt")) or None,
        "seo_title": text(incoming.get("seo_title")) or None,
        "seo_description": text(incoming.get("seo_description")) or None,
        "focus_keywords": incoming.get("focus_keywords") or [],
        "updated_at": incoming.get("updated_at"),
        "notes": f"Synced from WordPress ({incoming.get('post_type', 'post')}).",
    }

    if previous:
        for field in EDITORIAL_FIELDS:
            record[field] = previous.get(field)
        record["needs_review"] = previous.get("needs_review", False)
        status = "updated"
    else:
        record.update(infer(record["title"], incoming.get("content", "")[:3000]))
        status = "new"

    body = (incoming.get("content") or "")[:4000]
    searchable = " ".join(
        filter(
            None,
            [
                record["title"], record["title"],
                record["seo_title"], record["seo_description"], record["excerpt"],
                " ".join(record["focus_keywords"]),
                " ".join(incoming.get("categories") or []),
                " ".join(incoming.get("tags") or []),
                record.get("content_type"), record.get("primary_destination"),
                " ".join(record.get("related_destinations") or []),
                record.get("primary_topic") or "",
                " ".join(record.get("subtopics") or []),
                " ".join(record.get("traveler_intents") or []),
                " ".join(record.get("related_questions") or []),
                body,
            ],
        )
    )
    record["search_text"] = searchable
    record["tokens"] = tokenise(searchable)
    return record, status


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync ComeMorocco content into the AI knowledge base")
    parser.add_argument("--url", default=os.getenv("WORDPRESS_URL", "https://comemorocco.com"))
    parser.add_argument("--secret", default=os.getenv("SYNC_SECRET"))
    parser.add_argument("--since", type=int, help="only pages modified in the last N days")
    parser.add_argument("--service", default=os.getenv("SERVICE_URL", "http://localhost:8000"))
    parser.add_argument("--admin-key", default=os.getenv("ADMIN_KEY"))
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-prune", action="store_true",
                        help="keep pages that are no longer published in WordPress")
    args = parser.parse_args()

    if not args.secret:
        sys.exit("No sync secret. Pass --secret or set SYNC_SECRET (see the plugin settings page).")

    since = None
    if args.since:
        since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.since)).strftime("%Y-%m-%dT%H:%M:%S")

    print(f"Fetching content from {args.url}" + (f" (changed since {since})" if since else ""))
    incoming = fetch_all(args.url, args.secret, since, args.timeout)
    if not incoming:
        print("Nothing returned. Check the plugin's post-type settings.")
        return 1

    data = json.loads(KNOWLEDGE.read_text(encoding="utf-8"))
    existing = {item["id"]: item for item in data["items"]}

    new_count = updated_count = 0
    for item in incoming:
        record, status = merge(existing, item)
        existing[record["id"]] = record
        if status == "new":
            new_count += 1
        else:
            updated_count += 1

    removed: list[str] = []
    # Only a full sync can tell what has been deleted; a --since run sees a
    # partial view and must not prune from it.
    if not args.no_prune and not since:
        live_ids = {str(item["id"]) for item in incoming}
        removed = [cid for cid in existing if cid not in live_ids]
        for cid in removed:
            del existing[cid]

    needs_review = [i for i in existing.values() if i.get("needs_review")]

    print(f"\n  new       {new_count}")
    print(f"  updated   {updated_count}")
    print(f"  removed   {len(removed)}")
    print(f"  total     {len(existing)}")
    if needs_review:
        print(f"\n  {len(needs_review)} page(s) await editorial review and will not be "
              f"recommended until classified:")
        for item in needs_review[:10]:
            print(f"    [{item['id']}] {item['title'][:66]}")

    if args.dry_run:
        print("\nDry run — nothing written.")
        return 0

    data["items"] = sorted(existing.values(), key=lambda i: int(i["id"]) if i["id"].isdigit() else 0)
    backup = KNOWLEDGE.with_suffix(".json.bak")
    backup.write_text(KNOWLEDGE.read_text(encoding="utf-8"), encoding="utf-8")
    KNOWLEDGE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nWritten to {KNOWLEDGE} (previous copy at {backup.name})")

    if args.admin_key:
        try:
            response = httpx.post(
                f"{args.service.rstrip('/')}/api/admin/reindex",
                headers={"X-Admin-Key": args.admin_key},
                timeout=30.0,
            )
            response.raise_for_status()
            print(f"Service reindexed: {response.json()}")
        except Exception as exc:  # noqa: BLE001
            print(f"Could not reindex the running service ({exc}). Restart it to pick up the change.")
    else:
        print("No admin key given — restart the service, or POST /api/admin/reindex, to load it.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
