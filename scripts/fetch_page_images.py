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
    OUT.write_text(json.dumps(found, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(found)}/{len(pages)} pages have a photo")


if __name__ == "__main__":
    main()
