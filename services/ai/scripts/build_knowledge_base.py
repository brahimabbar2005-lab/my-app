#!/usr/bin/env python3
"""Build the ComeMorocco AI runtime knowledge base from the source spreadsheets.

    python scripts/build_knowledge_base.py

Reads (from data/source/):
    06_COMEMOROCCO_CONTENT_MAP.xlsx   240 content items + intent/destination maps
    07_AFFILIATE_MAP.xlsx             27 affiliate programs + 77 GYG activities
    05_GOLDEN_QUESTIONS.xlsx          213 golden questions + 10 multi-turn tests

Writes (to data/knowledge/):
    content.json      retrievable ComeMorocco pages with linking rules
    affiliates.json   affiliate programs + activities with recommendation gates
    golden.json       evaluation dataset
    manifest.json     counts, checksums, build time

Nothing is invented here. Every field is carried across from the source, with
"Not specified in source" and empty cells normalised to null. The one piece of
derived data is `search_text`, a concatenation of the fields the retriever
indexes, and `tokens`, its tokenised form.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import openpyxl
except ImportError:  # pragma: no cover
    sys.exit("openpyxl is required:  pip install openpyxl")

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source"
OUT = ROOT / "data" / "knowledge"

NOT_SPECIFIED = {
    "",
    "none",
    "nan",
    "n/a",
    "not specified",
    "not specified in source",
    "unknown / not specified",
    "unknown",
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def clean(value) -> str | None:
    """Normalise a spreadsheet cell to a string or None."""
    if value is None:
        return None
    # WordPress exports carry raw HTML entities ("Safe, Easy &amp; Affordable"),
    # and the widget renders titles as text, so they would show up literally.
    text = html.unescape(str(value)).strip()
    if text.lower() in NOT_SPECIFIED:
        return None
    return text


def split_list(value, separators: str = r"[;|]") -> list[str]:
    """Split a delimited cell into a clean list."""
    text = clean(value)
    if not text:
        return []
    parts = re.split(separators, text)
    return [p.strip() for p in parts if p.strip() and p.strip().lower() not in NOT_SPECIFIED]


def sheet_rows(workbook, name: str) -> list[dict]:
    """Return a sheet as a list of dicts keyed by its header row."""
    ws = workbook[name]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    # Some generated sheets carry a title row above the header; the header is the
    # first row where every cell is populated.
    header_index = 0
    for i, row in enumerate(rows[:5]):
        populated = [c for c in row if c not in (None, "")]
        if len(populated) >= max(3, len(row) - 2):
            header_index = i
            break
    header = [clean(c) or f"col_{i}" for i, c in enumerate(rows[header_index])]
    out = []
    for row in rows[header_index + 1 :]:
        if all(c is None or str(c).strip() == "" for c in row):
            continue
        out.append(dict(zip(header, row)))
    return out


TOKEN_RE = re.compile(r"[a-z0-9]+")

# Kept out of the index: they match everything and so rank nothing.
STOPWORDS = {
    "a", "about", "after", "all", "also", "am", "an", "and", "any", "are", "as",
    "at", "be", "been", "before", "being", "best", "between", "but", "by", "can",
    "do", "does", "for", "from", "get", "go", "going", "good", "has", "have",
    "how", "i", "if", "in", "into", "is", "it", "its", "just", "know", "like",
    "me", "more", "most", "much", "my", "need", "no", "not", "of", "on", "one",
    "only", "or", "our", "out", "over", "should", "so", "some", "than", "that",
    "the", "their", "them", "then", "there", "these", "they", "this", "to", "up",
    "us", "use", "very", "want", "was", "we", "what", "when", "where", "which",
    "who", "why", "will", "with", "would", "you", "your", "guide", "morocco",
    "moroccan", "travel", "traveler", "traveller", "trip",
}


def tokenise(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 2]


# --------------------------------------------------------------------------
# content map
# --------------------------------------------------------------------------
# Rows in the content map that are wrong in a way that visibly misleads
# travellers. Corrected here so the build is right today, and printed on every
# build so they get fixed in the spreadsheet — at which point these entries
# should be deleted.
DATA_CORRECTIONS: dict[str, dict[str, str]] = {
    # The blog *index* page is typed "Weather / Seasons Guide", Core priority,
    # "Strong support", "Usually link". It is a listing of posts, and with that
    # labelling it won almost every weather question.
    "https://comemorocco.com/blog/": {
        "content_type": "Other",
        "link_behavior": "Do not proactively link",
        "reason": "blog index page mislabelled as a Core weather guide",
    },
}


def build_content() -> list[dict]:
    wb = openpyxl.load_workbook(SOURCE / "06_COMEMOROCCO_CONTENT_MAP.xlsx", read_only=True)
    items = []
    for row in sheet_rows(wb, "Content Map"):
        content_id = clean(row.get("Content ID"))
        url = clean(row.get("Permalink")) or clean(row.get("URL"))
        title = clean(row.get("Title"))
        if not content_id or not url or not title:
            continue

        item = {
            "id": str(content_id),
            "title": title,
            "url": url,
            "excerpt": clean(row.get("Excerpt")),
            "seo_title": clean(row.get("Rank Math Title")),
            "seo_description": clean(row.get("Rank Math Description")),
            "focus_keywords": split_list(row.get("Rank Math Focus Keyword"), r"[;,|]"),
            "content_type": clean(row.get("Content Type")),
            "primary_destination": clean(row.get("Primary Destination")),
            "related_destinations": split_list(row.get("Related Destinations")),
            "primary_topic": clean(row.get("Primary Topic")),
            "subtopics": split_list(row.get("Subtopics")),
            "traveler_intents": split_list(row.get("Traveler Intent")),
            "traveler_types": split_list(row.get("Traveler Types")),
            "related_questions": split_list(row.get("Related Traveler Questions"), r"\|"),
            "when_to_recommend": clean(row.get("When to Recommend")),
            "when_not_to_recommend": clean(row.get("When NOT to Recommend")),
            "anchor_texts": split_list(row.get("Natural Anchor Text")),
            "related_ids": split_list(row.get("Related Content IDs")),
            "priority": clean(row.get("Content Priority")) or "Low",
            "affiliate_relevant": (clean(row.get("Affiliate Relevant")) or "No"),
            "affiliate_type": clean(row.get("Affiliate Type")),
            "time_sensitivity": clean(row.get("Time Sensitivity")) or "Low",
            "live_data_required": clean(row.get("Live Data Required")) or "No",
            "ai_content_support": clean(row.get("AI Content Support")) or "Unclear",
            "link_behavior": clean(row.get("Recommended Link Behavior")) or "Do not proactively link",
            "notes": clean(row.get("Content Notes")),
        }

        searchable = " ".join(
            filter(
                None,
                [
                    item["title"],
                    item["title"],  # title weighted x2
                    item["seo_title"],
                    item["seo_description"],
                    item["excerpt"],
                    " ".join(item["focus_keywords"]),
                    item["content_type"],
                    item["primary_destination"],
                    " ".join(item["related_destinations"]),
                    item["primary_topic"],
                    " ".join(item["subtopics"]),
                    " ".join(item["traveler_intents"]),
                    " ".join(item["traveler_types"]),
                    " ".join(item["related_questions"]),
                ],
            )
        )
        item["search_text"] = searchable
        item["tokens"] = tokenise(searchable)

        correction = DATA_CORRECTIONS.get(item["url"].rstrip("/") + "/")
        if correction:
            for field, value in correction.items():
                if field != "reason":
                    item[field] = value
            item["corrected"] = correction["reason"]
        items.append(item)

    # Auxiliary sheets: destination coverage tells the link engine which
    # destinations actually have depth behind them.
    coverage = {}
    for row in sheet_rows(wb, "Destination Map"):
        dest = clean(row.get("Destination"))
        if not dest:
            continue
        coverage[dest.lower()] = {
            "destination": dest,
            "item_count": int(row.get("Number of related content items") or 0),
            "core_ids": split_list(row.get("Core content IDs")),
            "important_ids": split_list(row.get("Important content IDs")),
            "topics": split_list(row.get("Main topics covered")),
            "weak_topics": clean(row.get("Missing/weak topic signals")),
        }

    intent_map = {}
    for row in sheet_rows(wb, "Intent Map"):
        intent = clean(row.get("Intent"))
        if not intent:
            continue
        intent_map[intent.lower()] = {
            "intent": intent,
            "content_ids": split_list(row.get("Relevant Content IDs")),
            "link_behavior": clean(row.get("Link Behavior")),
        }

    gaps = []
    if "Content Gaps" in wb.sheetnames:
        for row in sheet_rows(wb, "Content Gaps"):
            values = {k: clean(v) for k, v in row.items()}
            if any(values.values()):
                gaps.append(values)

    wb.close()
    return items, coverage, intent_map, gaps


# --------------------------------------------------------------------------
# affiliates
# --------------------------------------------------------------------------
def build_affiliates() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    path = SOURCE / "07_AFFILIATE_MAP.xlsx"
    if not path.exists():
        sys.exit(
            "data/source/07_AFFILIATE_MAP.xlsx is missing.\n"
            "Generate it first:  python scripts/generate_affiliate_map.py"
        )
    wb = openpyxl.load_workbook(path, read_only=True)

    programs = []
    for row in sheet_rows(wb, "Affiliate Map"):
        aff_id = clean(row.get("Affiliate ID"))
        if not aff_id or not aff_id.startswith("AFF"):
            continue
        link = clean(row.get("Affiliate Link(s)"))
        # Two source links carry a "Name: " prefix; keep the raw value but also
        # expose the bare URL the widget can actually use.
        url = None
        if link:
            match = re.search(r"https?://\S+", link)
            url = match.group(0) if match else None
        program = {
            "id": aff_id,
            "name": clean(row.get("Affiliate Program")),
            "category": clean(row.get("Affiliate Category")),
            "description": clean(row.get("Description (Source)")),
            "raw_link": link,
            "url": url,
            "widget_code": clean(row.get("Widget Code")),
            "use_case": clean(row.get("Primary Use Case")),
            "intents": clean(row.get("Relevant Traveler Intent")),
            "destinations": clean(row.get("Relevant Destinations")),
            "when_to_recommend": clean(row.get("When to Recommend")),
            "when_not_to_recommend": clean(row.get("When NOT to Recommend")),
            "traveler_types": split_list(row.get("Relevant Traveler Types"), r"[;,]"),
            "commercial_intent": clean(row.get("Commercial Intent")) or "Medium",
            "live_data_required": clean(row.get("Live Data Required")) or "No",
            "disclosure_required": clean(row.get("Disclosure Required")) or "Yes",
            "presentation": clean(row.get("Preferred Presentation")),
            "notes": clean(row.get("Notes")),
            "mapping_basis": clean(row.get("Source / Mapping Basis")),
        }
        program["usable"] = bool(program["url"])
        text = " ".join(filter(None, [program["name"], program["category"], program["use_case"], program["intents"]]))
        program["tokens"] = tokenise(text)
        programs.append(program)

    activities = []
    for row in sheet_rows(wb, "GetYourGuide Activities"):
        gyg_id = clean(row.get("GYG Activity ID"))
        if not gyg_id or not gyg_id.startswith("GYG"):
            continue
        link = clean(row.get("Affiliate Link"))
        activity = {
            "id": gyg_id,
            "name": clean(row.get("Activity")),
            "url": link if link and link.startswith("http") else None,
            "category": clean(row.get("Activity Category")),
            "destination": clean(row.get("Destination")),
            "intents": clean(row.get("Relevant Traveler Intent")),
            "traveler_types": split_list(row.get("Relevant Traveler Types"), r"[;,]"),
            "when_to_recommend": clean(row.get("When to Recommend")),
            "when_not_to_recommend": clean(row.get("When NOT to Recommend")),
            "commercial_intent": clean(row.get("Commercial Intent")) or "Medium",
            "presentation": clean(row.get("Preferred Presentation")),
            "mapping_basis": clean(row.get("Source / Mapping Basis")),
            "review_status": clean(row.get("Review Status")),
        }
        text = " ".join(filter(None, [activity["name"], activity["category"], activity["destination"]]))
        activity["tokens"] = tokenise(text)
        # Rows flagged for review, or with an unconfirmed destination, must not be
        # surfaced to travellers until a human has checked them.
        status = (activity["review_status"] or "").lower()
        activity["usable"] = bool(activity["url"]) and "critical" not in status
        activities.append(activity)

    intent_rows = []
    for row in sheet_rows(wb, "Intent Map"):
        values = {k: clean(v) for k, v in row.items()}
        if any(values.values()):
            intent_rows.append(values)

    review = []
    for row in sheet_rows(wb, "Review Notes"):
        values = {k: clean(v) for k, v in row.items()}
        if any(values.values()):
            review.append(values)

    wb.close()
    return programs, activities, intent_rows, review


# --------------------------------------------------------------------------
# golden questions
# --------------------------------------------------------------------------
def build_golden() -> tuple[list[dict], list[dict], list[dict]]:
    wb = openpyxl.load_workbook(SOURCE / "05_GOLDEN_QUESTIONS.xlsx", read_only=True)

    questions = []
    for row in sheet_rows(wb, "Golden Questions"):
        qid = clean(row.get("ID"))
        question = clean(row.get("User Question"))
        if not qid or not question:
            continue
        questions.append(
            {
                "id": qid,
                "category": clean(row.get("Category")),
                "subcategory": clean(row.get("Subcategory")),
                "question": question,
                "intent": clean(row.get("Intent")),
                "traveler_type": clean(row.get("Traveler Type")),
                "trip_context": clean(row.get("Trip Context")),
                "source_response": clean(row.get("Original Response")),
                "extracted_advice": clean(row.get("Extracted Advice")),
                "key_facts": clean(row.get("Key Facts / Details")),
                "recommendation": clean(row.get("Recommendation")),
                "warning": clean(row.get("Important Warning")),
                "evidence_type": clean(row.get("Evidence Type")),
                "confidence_note": clean(row.get("Confidence / Reliability Note")),
                "live_data_required": (clean(row.get("Live Data Required")) or "No"),
                "safety_sensitive": (clean(row.get("Safety Sensitive")) or "No"),
                "affiliate_relevant": (clean(row.get("Affiliate Relevant")) or "No"),
                "affiliate_type": clean(row.get("Affiliate Type")),
                "content_opportunity": clean(row.get("ComeMorocco Content Opportunity")),
                "must_not_do": clean(row.get("Must NOT Do")),
                "natural_answer_requirement": clean(row.get("Natural Answer Requirement")),
                "difficulty": clean(row.get("Difficulty")) or "Medium",
                "language": clean(row.get("Multilingual Test")) or "English",
                "evaluation_notes": clean(row.get("Evaluation Notes")),
            }
        )

    multi_turn = []
    for row in sheet_rows(wb, "Multi-Turn Tests"):
        tid = clean(row.get("Test ID"))
        if not tid:
            continue
        turns = [clean(row.get(f"Turn {i}")) for i in range(1, 5)]
        multi_turn.append(
            {
                "id": tid,
                "context": clean(row.get("Source Context")),
                "turns": [t for t in turns if t],
                "expected_behaviour": clean(row.get("Expected Behaviour")),
                "tests": clean(row.get("What This Tests")),
            }
        )

    source_examples = []
    for row in sheet_rows(wb, "Source Examples"):
        sid = clean(row.get("Example ID"))
        if not sid:
            continue
        source_examples.append(
            {
                "id": sid,
                "question": clean(row.get("Question")),
                "response": clean(row.get("Original Response")),
                "why_it_matters": clean(row.get("Why It Matters")),
            }
        )

    wb.close()
    return questions, multi_turn, source_examples


# --------------------------------------------------------------------------
def write_json(name: str, payload) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def main() -> None:
    content, coverage, intent_map, gaps = build_content()
    programs, activities, aff_intents, review = build_affiliates()
    questions, multi_turn, examples = build_golden()

    files = {
        "content.json": {
            "items": content,
            "destination_coverage": coverage,
            "intent_map": intent_map,
            "content_gaps": gaps,
        },
        "affiliates.json": {
            "programs": programs,
            "activities": activities,
            "intent_map": aff_intents,
            "review_notes": review,
        },
        "golden.json": {
            "questions": questions,
            "multi_turn": multi_turn,
            "source_examples": examples,
        },
    }

    manifest = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": {
            "content_items": len(content),
            "destinations": len(coverage),
            "content_gaps": len(gaps),
            "affiliate_programs": len(programs),
            "affiliate_programs_usable": sum(1 for p in programs if p["usable"]),
            "activities": len(activities),
            "activities_usable": sum(1 for a in activities if a["usable"]),
            "golden_questions": len(questions),
            "multi_turn_tests": len(multi_turn),
            "source_examples": len(examples),
        },
        "files": {},
    }

    for name, payload in files.items():
        path = write_json(name, payload)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        manifest["files"][name] = {"sha256_16": digest, "bytes": path.stat().st_size}

    write_json("manifest.json", manifest)

    corrected = [i for i in content if i.get("corrected")]
    if corrected:
        print(f"Applied {len(corrected)} data correction(s) — fix these in the content map:")
        for item in corrected:
            print(f"  [{item['id']}] {item['url']}  ({item['corrected']})")
        print()

    print("Knowledge base built in", OUT)
    for key, value in manifest["counts"].items():
        print(f"  {key:28} {value}")


if __name__ == "__main__":
    main()
