#!/usr/bin/env python3
"""Build the platform catalog from the AI knowledge base.

    python3 scripts/generate_catalog.py          # write
    python3 scripts/generate_catalog.py --check  # fail if outputs are stale

Source of truth: services/ai/data/knowledge/{content,affiliates}.json (built
from the editorial spreadsheets). Outputs:

  apps/mobile/src/data/catalog.generated.json
      destinations, listings and articles for the app's offline/mock data.
      Contains NO partner URLs — the app only knows listing ids and opens
      them through the worker's /go redirect.

  workers/platform/src/affiliate-links.generated.json
      listing id -> partner URL, used server-side by /go when Supabase is not
      configured (and as the seed for affiliate_links).

  supabase/seed/seed.sql
      destinations, affiliate programs/links, listings and content refs.

No prices are generated: the source has none, and the app must not invent
them (Master Plan §15). Listings show "View options" instead.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "services" / "ai" / "data" / "knowledge"
OUT_MOBILE = ROOT / "apps" / "mobile" / "src" / "data" / "catalog.generated.json"
OUT_WORKER = ROOT / "workers" / "platform" / "src" / "affiliate-links.generated.json"
OUT_SQL = ROOT / "supabase" / "seed" / "seed.sql"

# Master Plan §8 destinations. `match` = words that map source rows here.
DESTINATIONS = [
    {"id": "marrakech", "name": {"en": "Marrakech", "fr": "Marrakech", "ar": "مراكش", "es": "Marrakech"},
     "region": "Marrakech-Safi", "lat": 31.6295, "lng": -7.9811, "hue": "#B4462F",
     "tagline": {"en": "Souks, riads and the Atlas on the horizon", "fr": "Souks, riads et l'Atlas à l'horizon", "ar": "أسواق ورياضات والأطلس في الأفق", "es": "Zocos, riads y el Atlas en el horizonte"}, "match": ["marrakech", "marrakesh", "agafay", "palmeraie", "rak"]},
    {"id": "fes", "name": {"en": "Fes", "fr": "Fès", "ar": "فاس", "es": "Fez"},
     "region": "Fès-Meknès", "lat": 34.0181, "lng": -5.0078, "hue": "#3450A1",
     "tagline": {"en": "The world's largest living medina", "fr": "La plus grande médina vivante du monde", "ar": "أكبر مدينة عتيقة مأهولة في العالم", "es": "La medina viva más grande del mundo"}, "match": ["fes", "fez"]},
    {"id": "chefchaouen", "name": {"en": "Chefchaouen", "fr": "Chefchaouen", "ar": "شفشاون", "es": "Chefchaouen"},
     "region": "Tanger-Tétouan-Al Hoceïma", "lat": 35.1688, "lng": -5.2636, "hue": "#4F7BC8",
     "tagline": {"en": "The blue city in the Rif mountains", "fr": "La ville bleue au cœur du Rif", "ar": "المدينة الزرقاء في جبال الريف", "es": "La ciudad azul en las montañas del Rif"}, "match": ["chefchaouen"]},
    {"id": "merzouga", "name": {"en": "Merzouga & Sahara", "fr": "Merzouga et Sahara", "ar": "مرزوكة والصحراء", "es": "Merzouga y Sáhara"},
     "region": "Drâa-Tafilalet", "lat": 31.0802, "lng": -4.0134, "hue": "#C9832E",
     "tagline": {"en": "Dunes of Erg Chebbi and nights under the stars", "fr": "Les dunes de l'Erg Chebbi et des nuits sous les étoiles", "ar": "كثبان عرق الشبي وليالٍ تحت النجوم", "es": "Las dunas del Erg Chebbi y noches bajo las estrellas"}, "match": ["merzouga", "erg chebbi", "sahara"]},
    {"id": "essaouira", "name": {"en": "Essaouira", "fr": "Essaouira", "ar": "الصويرة", "es": "Esauira"},
     "region": "Marrakech-Safi", "lat": 31.5085, "lng": -9.7595, "hue": "#1F7A63",
     "tagline": {"en": "Windswept ramparts, surf and seafood", "fr": "Remparts battus par le vent, surf et fruits de mer", "ar": "أسوار تعصف بها الرياح وركوب الأمواج والمأكولات البحرية", "es": "Murallas azotadas por el viento, surf y marisco"}, "match": ["essaouira"]},
    {"id": "casablanca", "name": {"en": "Casablanca", "fr": "Casablanca", "ar": "الدار البيضاء", "es": "Casablanca"},
     "region": "Casablanca-Settat", "lat": 33.5731, "lng": -7.5898, "hue": "#4A403A",
     "tagline": {"en": "Art deco, the Atlantic and Hassan II Mosque", "fr": "Art déco, l'Atlantique et la mosquée Hassan II", "ar": "فن الآرت ديكو والأطلسي ومسجد الحسن الثاني", "es": "Art déco, el Atlántico y la mezquita Hassan II"}, "match": ["casablanca"]},
    {"id": "rabat", "name": {"en": "Rabat", "fr": "Rabat", "ar": "الرباط", "es": "Rabat"},
     "region": "Rabat-Salé-Kénitra", "lat": 34.0209, "lng": -6.8416, "hue": "#2A3F8F",
     "tagline": {"en": "The calm, green capital by the sea", "fr": "La capitale calme et verte au bord de l'océan", "ar": "العاصمة الهادئة الخضراء على البحر", "es": "La capital tranquila y verde junto al mar"}, "match": ["rabat"]},
    {"id": "tangier", "name": {"en": "Tangier", "fr": "Tanger", "ar": "طنجة", "es": "Tánger"},
     "region": "Tanger-Tétouan-Al Hoceïma", "lat": 35.7595, "lng": -5.8340, "hue": "#6A4C93",
     "tagline": {"en": "Where Africa meets Europe", "fr": "Là où l'Afrique rencontre l'Europe", "ar": "حيث تلتقي إفريقيا بأوروبا", "es": "Donde África se encuentra con Europa"}, "match": ["tangier", "tanger"]},
    {"id": "agadir", "name": {"en": "Agadir & Taghazout", "fr": "Agadir et Taghazout", "ar": "أكادير وتغازوت", "es": "Agadir y Taghazout"},
     "region": "Souss-Massa", "lat": 30.4278, "lng": -9.5981, "hue": "#E0A526",
     "tagline": {"en": "Year-round sun and world-class surf", "fr": "Soleil toute l'année et surf de classe mondiale", "ar": "شمس طوال العام وأمواج عالمية لركوب الأمواج", "es": "Sol todo el año y surf de primer nivel"}, "match": ["agadir", "taghazout", "timlalin", "legzira"]},
    {"id": "ouarzazate", "name": {"en": "Ouarzazate", "fr": "Ouarzazate", "ar": "ورزازات", "es": "Uarzazat"},
     "region": "Drâa-Tafilalet", "lat": 30.9335, "lng": -6.9370, "hue": "#9C3B26",
     "tagline": {"en": "Kasbahs, film sets and the road to the desert", "fr": "Kasbahs, studios de cinéma et la route du désert", "ar": "قصبات واستوديوهات سينما والطريق إلى الصحراء", "es": "Kasbahs, platós de cine y la ruta al desierto"}, "match": ["ouarzazate", "ait benhaddou", "draa", "dades", "todra"]},
    {"id": "dakhla", "name": {"en": "Dakhla", "fr": "Dakhla", "ar": "الداخلة", "es": "Dajla"},
     "region": "Dakhla-Oued Ed-Dahab", "lat": 23.6848, "lng": -15.9579, "hue": "#2B8C9E",
     "tagline": {"en": "Lagoon kitesurfing where the desert meets the ocean", "fr": "Kitesurf sur la lagune, là où le désert rencontre l'océan", "ar": "ركوب الأمواج الشراعية في البحيرة حيث تلتقي الصحراء بالمحيط", "es": "Kitesurf en la laguna donde el desierto se une al océano"}, "match": ["dakhla"]},
]

# Book tab categories for partner programs (Master Plan §9).
PROGRAM_CATEGORY = {
    "Accommodation": "stay",
    "Hostels": "stay",
    "Car Rental": "car",
    "Airport Transfer": "transfer",
    "Private Transfer": "transfer",
    "Tours & Activities": "experience",
    "Attractions": "experience",
}
ACTIVITY_TRANSFER = {"Airport Transfer"}
# Guides tied to a past event (AFCON 2025) stay searchable but are never featured.
DATED_EVENT = re.compile(r"\bAFCON\b", re.IGNORECASE)
# Index, legal and site-utility pages are not guides.
UTILITY_PAGE = re.compile(
    r"comemorocco\.com/(?:destinations|blog|about[^/]*|contact|privacy[^/]*|terms[^/]*|cookie[^/]*|"
    r"disclaimer|affiliate[^/]*|services|sitemap[^/]*|faq)/?$"
)


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _mentions(text: str, words: list[str]) -> bool:
    # Whole words only: "fes" must not match "festivals".
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def match_destination(text: str) -> str | None:
    lowered = (text or "").lower()
    # "X — from Y": the experience happens in X.
    primary = lowered.split("— from")[0].split("- from")[0]
    for dest in DESTINATIONS:
        if _mentions(primary, dest["match"]):
            return dest["id"]
    for dest in DESTINATIONS:
        if _mentions(lowered, dest["match"]):
            return dest["id"]
    return None


def partner_of(url: str) -> str:
    host = re.sub(r"^https?://", "", url).split("/")[0]
    if "gyg.me" in host or "getyourguide" in host:
        return "getyourguide"
    return host.split(".")[0] if host.endswith("tpx.li") else host


def build():
    content = json.loads((KNOWLEDGE / "content.json").read_text())["items"]
    affiliates = json.loads((KNOWLEDGE / "affiliates.json").read_text())

    listings, links, programs = [], {}, []

    for program in affiliates["programs"]:
        programs.append({
            "id": program["id"], "name": program["name"], "category": program["category"],
            "usable": bool(program["usable"]), "url": program["url"],
        })
        category = PROGRAM_CATEGORY.get(program["category"])
        if not category or not program["usable"] or not program["url"].startswith("http"):
            continue
        links[program["id"]] = {"url": program["url"], "partner": partner_of(program["url"]),
                                "program_id": program["id"], "kind": "program"}
        listings.append({
            "id": program["id"], "kind": "program", "category": category,
            "title": program["name"], "subtitle": program["category"],
            "destination": None, "partner": program["name"],
        })

    seen_urls: set[str] = set()
    for activity in affiliates["activities"]:
        url = activity.get("url") or ""
        if not activity.get("usable") or not url.startswith("http"):
            continue
        links[activity["id"]] = {"url": url, "partner": partner_of(url), "program_id": None, "kind": "activity"}
        # The README warns 12 gyg.me short links are shared across activities;
        # only the first listing per URL is shown so one link is never offered
        # under two different names.
        if url in seen_urls:
            continue
        seen_urls.add(url)
        listings.append({
            "id": activity["id"], "kind": "activity",
            "category": "transfer" if activity["category"] in ACTIVITY_TRANSFER else "experience",
            "title": activity["name"], "subtitle": activity["category"],
            "destination": match_destination(activity.get("destination") or ""),
            "partner": "GetYourGuide" if "gyg.me" in url else partner_of(url),
        })

    articles = []
    for item in content:
        if item.get("link_behavior") == "Do not proactively link" or item.get("priority") not in {"Core", "Important"}:
            continue
        dest = match_destination(item.get("primary_destination") or "") or match_destination(item["title"])
        if item["url"].rstrip("/") == "https://comemorocco.com" or not item["url"].startswith("https://comemorocco.com/"):
            continue
        if item.get("content_type") == "Other" or UTILITY_PAGE.search(item["url"]):
            continue
        articles.append({
            "id": f"wp-{item['id']}", "wordpress_post_id": int(item["id"]) if str(item["id"]).isdigit() else None,
            "title": item["title"], "excerpt": (item.get("excerpt") or item.get("seo_description") or "")[:220],
            "canonical_url": item["url"], "destination": dest, "topic": item.get("primary_topic"),
        })

    # Real guides first: short titles ("Hotels", "Camel Riding") are thin
    # category pages. Then destination-specific before country-wide.
    articles.sort(key=lambda a: (len(a["title"].split()) < 4, bool(DATED_EVENT.search(a["title"])),
                                 a["destination"] is None))

    destinations = []
    for dest in DESTINATIONS:
        own = [a for a in articles if a["destination"] == dest["id"]]
        named = [a for a in own if _mentions(a["title"].lower(), dest["match"])]
        # The site's own destination hub (/destinations/<city>/) is the guide
        # when it exists; otherwise the best evergreen guide naming the city.
        # Matched on the URL slug, not the row's destination tag: the source
        # tags the Dakhla hub as "Sahara Desert".
        hub_slugs = {dest["id"], *(slug(w) for w in dest["match"])}
        hub = next((a for a in articles
                    if (m := re.search(r"/destinations/([a-z-]+)/?$", a["canonical_url"])) and m.group(1) in hub_slugs),
                   None)
        guide = (
            hub
            or next((a for a in named if not DATED_EVENT.search(a["title"])
                     and re.search(r"\b(guide|things to do|travel)\b", a["title"].lower())), None)
            or next(iter(named), None)
        )
        destinations.append({k: v for k, v in dest.items() if k != "match"} | {
            "guide_url": guide["canonical_url"] if guide else None,
            "listing_count": sum(1 for listing in listings if listing["destination"] == dest["id"]),
            "article_count": sum(1 for a in articles if a["destination"] == dest["id"]),
        })

    catalog = {"_generated_by": "scripts/generate_catalog.py", "destinations": destinations,
               "listings": listings, "articles": articles}
    return catalog, links, programs


def sql_str(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def build_sql(catalog, links, programs) -> str:
    out = ["-- Generated by scripts/generate_catalog.py — do not edit by hand.",
           "-- Source: services/ai/data/knowledge (editorial spreadsheets).", "begin;", ""]
    out.append("insert into public.destinations (id, name, region, lat, lng, tagline, hue, guide_url) values")
    rows = [f"  ({sql_str(d['id'])}, {sql_str(json.dumps(d['name'], ensure_ascii=False))}::jsonb, {sql_str(d['region'])}, "
            f"{d['lat']}, {d['lng']}, {sql_str(json.dumps(d['tagline'], ensure_ascii=False))}::jsonb, "
            f"{sql_str(d['hue'])}, {sql_str(d['guide_url'])})"
            for d in catalog["destinations"]]
    out.append(",\n".join(rows) + "\non conflict (id) do update set name = excluded.name, region = excluded.region, "
               "lat = excluded.lat, lng = excluded.lng, tagline = excluded.tagline, hue = excluded.hue, "
               "guide_url = excluded.guide_url;\n")

    out.append("insert into public.affiliate_programs (id, name, category, usable, conversion_capability) values")
    rows = [f"  ({sql_str(p['id'])}, {sql_str(p['name'])}, {sql_str(p['category'])}, {sql_str(p['usable'])}, 'report_import')"
            for p in programs]
    out.append(",\n".join(rows) + "\non conflict (id) do update set name = excluded.name, category = excluded.category, "
               "usable = excluded.usable;\n")

    out.append("insert into public.listings (id, kind, category, title, subtitle, destination_id, partner_name, status) values")
    rows = [f"  ({sql_str(li['id'])}, {sql_str(li['kind'])}, {sql_str(li['category'])}, {sql_str(li['title'])}, "
            f"{sql_str(li['subtitle'])}, {sql_str(li['destination'])}, {sql_str(li['partner'])}, 'published')"
            for li in catalog["listings"]]
    out.append(",\n".join(rows) + "\non conflict (id) do update set title = excluded.title, subtitle = excluded.subtitle, "
               "category = excluded.category, destination_id = excluded.destination_id;\n")

    # Links exist for every usable id (including de-duplicated activities);
    # only ids that are listings get a row, since affiliate_links references listings.
    listing_ids = {li["id"] for li in catalog["listings"]}
    out.append("insert into public.affiliate_links (listing_id, program_id, partner, url, active) values")
    rows = [f"  ({sql_str(lid)}, {sql_str(link['program_id'])}, {sql_str(link['partner'])}, {sql_str(link['url'])}, true)"
            for lid, link in sorted(links.items()) if lid in listing_ids]
    out.append(",\n".join(rows) + "\non conflict (listing_id) do update set url = excluded.url, partner = excluded.partner;\n")

    out.append("insert into public.content_items (id, source, wordpress_post_id, canonical_url, title, excerpt, destination_id, topic) values")
    rows = [f"  ({sql_str(a['id'])}, 'wordpress', {sql_str(a['wordpress_post_id'])}, {sql_str(a['canonical_url'])}, "
            f"{sql_str(a['title'])}, {sql_str(a['excerpt'])}, {sql_str(a['destination'])}, {sql_str(a['topic'])})"
            for a in catalog["articles"]]
    out.append(",\n".join(rows) + "\non conflict (id) do update set title = excluded.title, excerpt = excluded.excerpt, "
               "canonical_url = excluded.canonical_url, destination_id = excluded.destination_id;\n")
    out.append("commit;\n")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    catalog, links, programs = build()
    outputs = {
        OUT_MOBILE: json.dumps(catalog, indent=1, ensure_ascii=False) + "\n",
        OUT_WORKER: json.dumps({"_generated_by": "scripts/generate_catalog.py", "links": links},
                               indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        OUT_SQL: build_sql(catalog, links, programs),
    }
    stale = []
    for path, text in outputs.items():
        if args.check:
            if not path.exists() or path.read_text() != text:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            print(f"wrote {path.relative_to(ROOT)}")
    if not args.check:
        print(f"{len(catalog['destinations'])} destinations, {len(catalog['listings'])} listings, "
              f"{len(catalog['articles'])} articles, {len(links)} affiliate links")
    if stale:
        print("stale generated files: " + ", ".join(stale) + " — run python3 scripts/generate_catalog.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
