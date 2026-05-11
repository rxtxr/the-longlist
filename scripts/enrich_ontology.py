#!/usr/bin/env python3
"""Enrich all knowledge entries with ontology metadata.
Adds entity_type, entity_subtype, geo_region, era_from/to, typed relations.
Pure heuristic — no API calls. Safe to re-run (skips already-enriched fields)."""
import warnings; warnings.filterwarnings("ignore")
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import frontmatter as fm
from config import CATEGORIES, KNOWLEDGE_DIR, WIKI_OBSIDIAN_DIR
from tools.ontology import CATEGORY_ENTITY_TYPE, RELATION_TYPES

# ── Geo keyword rules (first match wins) ────────────────────────────────────
GEO_RULES = [
    ("madison_avenue", ["madison avenue", "madison ave", "fifth avenue"]),
    ("chicago_school",  ["chicago", "leo burnett"]),
    ("west_coast_us",   ["california", "san francisco", "los angeles", "west coast"]),
    ("soho_london",     ["soho london", "london", "british advertising"]),
    ("hamburg",         ["hamburger werbeszene", "hamburg"]),
    ("munich",          ["münchen", "munich", "muenchen", "bayerisch", "münchen"]),
    ("duesseldorf",     ["düsseldorf", "duesseldorf"]),
    ("frankfurt",       ["frankfurt"]),
    ("berlin",          ["berlin"]),
    ("zurich_basel",    ["zürich", "zurich", "zürichsee", "basel", "helvetia", "schweizer werbung"]),
    ("vienna",          ["wien ", "vienna", "österreich", "wiener"]),
    ("paris",           ["paris", "französisch"]),
]

# ── Era decade → (from, to) ──────────────────────────────────────────────────
_DECADE_MAP = {str(d): (d, d + 9) for d in range(1900, 2030, 10)}


def parse_era(era_str: str, title: str = "") -> tuple:
    s = str(era_str or "").strip() + " " + str(title or "")
    # Range: "1950-1970" or "1950–1970"
    m = re.search(r"(1[89]\d\d|20[0-2]\d)\s*[-–]\s*(1[89]\d\d|20[0-2]\d)", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    # Decade: "1960er" / "1960s"
    m = re.search(r"(1[89]\d|20[0-2])0(?:er|s)?", s)
    if m:
        decade_start = int(m.group(0)[:4])
        return decade_start, decade_start + 9
    # Single year
    m = re.search(r"(1[89]\d\d|20[0-2]\d)", s)
    if m:
        return int(m.group(1)), None
    return None, None


def detect_geo(text: str) -> str | None:
    t = text.lower()
    for region_id, keywords in GEO_RULES:
        for kw in keywords:
            if kw in t:
                return region_id
    return None


def detect_subtype(category: str, combined: str) -> str | None:
    subtypes_map = {
        "agencies": [
            ("holding",    ["wpp", "interpublic", "omnicom", "publicis holding", "holding"]),
            ("network",    ["netzwerk", "network", "globales", "world wide"]),
            ("digital",    ["digital", "interaktiv", "online-agentur"]),
            ("media",      ["media-agentur", "mediaplanung", "mediaeinkauf"]),
            ("direct",     ["direct marketing", "direktmarketing"]),
            ("boutique",   ["boutique", "kleine agentur", "unabhängige"]),
        ],
        "people": [
            ("creative_director", ["creative director", "kreativdirektor", "ecd", "chief creative"]),
            ("copywriter",        ["texter", "copywriter", "werbetexter"]),
            ("art_director",      ["art director", "art-director"]),
            ("strategist",        ["account planner", "strategieberater", "planning"]),
            ("founder",           ["gründer", "mitgründer", "gründete"]),
            ("photographer",      ["fotograf", "photographer", "fotografie"]),
        ],
        "eras": [
            ("scene",    ["szene", "werbeszene", "stadtkultur"]),
            ("movement", ["bewegung", "revolution", "kreativen revolution", "kreative welle"]),
            ("decade",   ["jahrzehnt", "1950er", "1960er", "1970er", "1980er", "1990er", "2000er"]),
        ],
        "technology": [
            ("print",     ["druckerei", "lithografie", "satz ", "drucktechnik"]),
            ("broadcast", ["fernsehen", "television", "rundfunk", "broadcast", "radiospot"]),
            ("digital",   ["computer", "digitalfotografie", "internet", "software"]),
            ("studio",    ["fotostudio", "fotoatelier", "aufnahmestudio"]),
        ],
        "philosophy": [
            ("strategy",     ["strategie", "planung", "account planning"]),
            ("methodology",  ["methode", "forschung", "marktforschung"]),
            ("movement",     ["bewegung", "strömung", "schule"]),
            ("principle",    ["prinzip", "philosophie", "grundsatz"]),
        ],
    }
    for subtype, keywords in subtypes_map.get(category, []):
        for kw in keywords:
            if kw in combined:
                return subtype
    return None


def infer_relation_type(src_cat: str, tgt_cat: str) -> str:
    if src_cat == "agencies" and tgt_cat == "people":
        return "employed"
    if src_cat == "people" and tgt_cat == "agencies":
        return "worked_at"
    if src_cat == "agencies" and tgt_cat == "agencies":
        return "competed_with"
    if src_cat == "people" and tgt_cat == "people":
        return "collaborated_with"
    if tgt_cat == "eras":
        return "belongs_to_era"
    if tgt_cat == "philosophy":
        return "exemplifies"
    if tgt_cat in ("work",):
        return "created"
    if tgt_cat == "scandals":
        return "involved_in"
    return "related"


def main():
    # Build title → (category, path) index for relation resolution
    title_index: dict[str, tuple] = {}
    for cat in CATEGORIES:
        cat_dir = KNOWLEDGE_DIR / cat
        if not cat_dir.exists():
            continue
        for f in cat_dir.glob("*.md"):
            try:
                post = fm.load(str(f))
                title = post.metadata.get("title", "")
                if title:
                    title_index[title.lower()] = (cat, f)
            except Exception:
                pass

    updated = 0
    for cat in CATEGORIES:
        cat_dir = KNOWLEDGE_DIR / cat
        if not cat_dir.exists():
            continue
        for f in sorted(cat_dir.glob("*.md")):
            try:
                post = fm.load(str(f))
                meta = post.metadata
                changed = False
                title = meta.get("title", f.stem)
                content_preview = post.content[:1200]
                combined = (title + " " + content_preview).lower()

                # entity_type
                if "entity_type" not in meta:
                    meta["entity_type"] = CATEGORY_ENTITY_TYPE.get(cat, "concept")
                    changed = True

                # entity_subtype
                if "entity_subtype" not in meta:
                    sub = detect_subtype(cat, combined)
                    if sub:
                        meta["entity_subtype"] = sub
                        changed = True

                # geo_region
                if "geo_region" not in meta:
                    geo = detect_geo(combined)
                    if geo:
                        meta["geo_region"] = geo
                        changed = True

                # era_from / era_to
                if "era_from" not in meta:
                    ef, et = parse_era(meta.get("era", ""), title)
                    if ef is not None:
                        meta["era_from"] = ef
                        changed = True
                    if et is not None:
                        meta["era_to"] = et
                        changed = True

                # typed relations from existing `related` list
                if "relations" not in meta:
                    related_list = meta.get("related", [])
                    relations = []
                    for related_title in related_list:
                        tgt_info = title_index.get(str(related_title).lower())
                        if tgt_info:
                            tgt_cat, tgt_path = tgt_info
                            rel_type = infer_relation_type(cat, tgt_cat)
                            relations.append({
                                "target_id": tgt_path.stem,
                                "type": rel_type,
                                "label": RELATION_TYPES.get(rel_type, {}).get("label", rel_type),
                            })
                    if relations:
                        meta["relations"] = relations
                        changed = True

                if changed:
                    post.metadata = meta
                    f.write_text(fm.dumps(post), encoding="utf-8")
                    updated += 1
                    print(f"  ✓ {cat}/{f.stem[:55]}")

            except Exception as e:
                print(f"  FEHLER {f.name}: {e}")

    print(f"\nAktualisiert: {updated} Einträge")


if __name__ == "__main__":
    main()
