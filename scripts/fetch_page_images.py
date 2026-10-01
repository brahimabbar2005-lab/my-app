#!/usr/bin/env python3
"""Collect the share image (og:image) of every comemorocco.com page the app
links to: destination guides and articles. The app shows these photos on its
cards; they are the site's own featured images, served from comemorocco.com.

    python3 scripts/fetch_page_images.py          # refresh the map
Writes apps/mobile/src/data/images.generated.json: {page url: image url}.
Pages without an og:image are left out (the app keeps its pattern tile).
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "apps/mobile/src/data/catalog.generated.json"
OUT = ROOT / "apps/mobile/src/data/images.generated.json"
OG_IMAGE = re.compile(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.I)
ALLOWED = "https://comemorocco.com/"
SRCSET = re.compile(r'srcset="([^"]+)"', re.I)
TARGET_WIDTH = 768  # phone cards are at most ~400 pt wide (x2 for retina)


def base_name(image_url: str) -> str:
    """'…/photo-1024x681.jpg' and '…/photo.jpg' share the base '…/photo'."""
    stem = image_url.rsplit(".", 1)[0]
    return re.sub(r"-\d+x\d+$", "", stem)


def smaller_copy(html: str, image: str) -> str:
    """WordPress serves resized copies of every upload in the page's srcset
    attributes; pick the one closest to TARGET_WIDTH (never upscaled)."""
    base = base_name(image)
    best: tuple[int, str] | None = None
    for srcset in SRCSET.findall(html):
        for candidate in srcset.split(","):
            parts = candidate.strip().split()
            if len(parts) != 2 or not parts[1].endswith("w") or base_name(parts[0]) != base:
                continue
            width = int(parts[1][:-1])
            score = abs(width - TARGET_WIDTH) + (1000 if width < 400 else 0)
            if best is None or score < best[0]:
                best = (score, parts[0])
    return best[1] if best else image


def media_library_copy(image: str) -> str:
    """Pages without a srcset: ask the WordPress media library for the
    upload's resized copies and take the one closest to TARGET_WIDTH."""
    name = base_name(image).rsplit("/", 1)[-1]
    query = urllib.parse.urlencode({"search": name, "per_page": 5})
    request = urllib.request.Request(f"{ALLOWED}wp-json/wp/v2/media?{query}", headers={"User-Agent": "ComeMorocco-app-catalog/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            items = json.loads(response.read())
    except Exception:  # noqa: BLE001 - keep the original image
        return image
    for item in items:
        if base_name(item.get("source_url", "")) != base_name(image):
            continue
        sizes = (item.get("media_details") or {}).get("sizes") or {}
        candidates = [(abs(v["width"] - TARGET_WIDTH) + (1000 if v["width"] < 400 else 0), v["source_url"])
                      for v in sizes.values() if v.get("width") and v.get("source_url", "").startswith(ALLOWED)]
        if candidates:
            return min(candidates)[1]
    return image


def og_image(url: str) -> str | None:
    request = urllib.request.Request(url, headers={"User-Agent": "ComeMorocco-app-catalog/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            html = response.read(1_500_000).decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001 - one bad page must not stop the run
        print(f"  skip {url}: {exc}", file=sys.stderr)
        return None
    match = OG_IMAGE.search(html)
    image = match.group(1) if match else None
    # Only the site's own uploads; never a third-party or tracking URL.
    if image and image.startswith(ALLOWED + "wp-content/uploads/"):
        smaller = smaller_copy(html, image)
        return smaller if smaller != image else media_library_copy(image)
    return None


STOP = {"and", "the", "from", "with", "tour", "tours", "trip", "day", "morocco", "moroccan", "guide",
        "best", "in", "of", "to", "a", "for", "your", "private", "small", "group", "full", "half"}


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2 and w not in STOP}


def listing_photos(catalog: dict, found: dict[str, str]) -> dict[str, str]:
    """Partner offers have no photos of their own: give each one the photo of
    the site page whose title (or address) shares the most words with the
    offer, else its destination guide's photo. Keys are "listing:<id>"."""
    pages = []
    for article in catalog["articles"]:
        image = found.get(article["canonical_url"])
        if image:
            pages.append((words(article["title"] + " " + article["canonical_url"]), image))
    guides = {d["id"]: found.get(d["guide_url"] or "") for d in catalog["destinations"]}
    out: dict[str, str] = {}
    for listing in catalog["listings"]:
        if listing.get("kind") != "activity":
            continue  # brand partners (Booking.com, car rental sites) keep their icon
        wanted = words(f"{listing['title']} {listing.get('subtitle', '')}")
        best = max(pages, key=lambda p: len(wanted & p[0]), default=None)
        if best and len(wanted & best[0]) >= 2:
            out[f"listing:{listing['id']}"] = best[1]
        elif guides.get(listing.get("destination") or ""):
            out[f"listing:{listing['id']}"] = guides[listing["destination"]]
    return out


def main() -> None:
    catalog = json.loads(CATALOG.read_text())
    pages = sorted(
        {d["guide_url"] for d in catalog["destinations"] if d.get("guide_url")}
        | {a["canonical_url"] for a in catalog["articles"] if a.get("canonical_url", "").startswith(ALLOWED)}
    )
    print(f"fetching og:image for {len(pages)} pages")
    with ThreadPoolExecutor(max_workers=8) as pool:
        images = dict(zip(pages, pool.map(og_image, pages)))
    found = {page: image for page, image in sorted(images.items()) if image}
    pages_with_photo = len(found)
    found.update(listing_photos(catalog, found))
    OUT.write_text(json.dumps(found, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {pages_with_photo}/{len(pages)} pages and "
          f"{len(found) - pages_with_photo} activities have a photo")


if __name__ == "__main__":
    main()
