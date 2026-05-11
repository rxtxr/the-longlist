"""
Fix citations: match source names in YAML frontmatter to actual URLs
from the search cache, then write a proper ## Quellen section into the
article with linked footnotes + access timestamps.

Usage:
  python scripts/fix_citations.py           # all articles
  python scripts/fix_citations.py --dry-run # preview only
  python scripts/fix_citations.py --cat agencies
"""
import re
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"
CACHE_DIR = Path(__file__).parent.parent / "waves" / "_search_cache"
TODAY = datetime.today().strftime("%d.%m.%Y")

CATEGORIES = ["agencies", "people", "eras", "work", "scandals", "technology", "life", "philosophy", "visuals"]


def _slug(text: str) -> str:
    s = text.lower()
    for old, new in [("ä","ae"),("ö","oe"),("ü","ue"),("ß","ss")]:
        s = s.replace(old, new)
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def _title_short(title: str) -> str:
    short = re.split(r"\s[—–-]\s", title)[0].strip()
    short = re.sub(r"\s*\([^)]*\d{4}[^)]*\)", "", short).strip()
    short = re.sub(r"\s*\([^)]*\)", "", short).strip()
    return short


def find_cached_results(title: str) -> list:
    """Load all cached search results whose filename contains a slug of the title."""
    short = _title_short(title)
    slug = _slug(short)

    # Try progressively shorter prefix matches
    prefixes = [slug[:35], slug[:25], slug[:15]]
    seen_urls: set = set()
    all_results = []

    for cache_file in CACHE_DIR.glob("*.json"):
        fname = cache_file.stem
        if any(p in fname for p in prefixes if len(p) >= 8):
            try:
                data = json.loads(cache_file.read_text())
                for r in data:
                    url = r.get("href", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(r)
            except Exception:
                pass

    return all_results


def _word_overlap(a: str, b: str) -> float:
    """Fraction of words from a that appear in b."""
    words_a = set(re.findall(r"\w{3,}", a.lower()))
    words_b = set(re.findall(r"\w{3,}", b.lower()))
    if not words_a:
        return 0.0
    return len(words_a & words_b) / len(words_a)


def match_source_to_url(source_name: str, cached_results: list) -> tuple:
    """Return (url, result_title) for the best-matching cached result."""
    # Strip leading "Quelle N: " prefix
    name = re.sub(r"^Quelle\s*\d+[.:]?\s*", "", source_name).strip()

    best_url = ""
    best_title = name
    best_score = 0.0

    for r in cached_results:
        r_title = r.get("title", "")
        r_body = r.get("body", "")
        r_href = r.get("href", "")

        search_text = f"{r_title} {r_body[:200]}"
        score = _word_overlap(name, search_text)

        # Bonus for URL domain match (e.g. source says "Wikipedia" → bonus for wikipedia.org)
        if "wikipedia" in name.lower() and "wikipedia.org" in r_href:
            score += 0.25
        if "ad age" in name.lower() and "adage.com" in r_href:
            score += 0.25
        if "campaign" in name.lower() and "campaign" in r_href:
            score += 0.2

        if score > best_score:
            best_score = score
            best_url = r_href
            best_title = r_title or name

    if best_score >= 0.25:
        return best_url, best_title
    return "", name


def parse_frontmatter(text: str) -> tuple:
    """Return (meta_text, body_text) or (None, text) if no frontmatter."""
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    return parts[1], parts[2]


def extract_numbered_sources(sources: list) -> dict:
    """
    Parse sources list like ['Quelle 1: Wikipedia ...', 'Quelle 3: ...']
    Returns {1: 'Wikipedia ...', 3: '...'} — only numbered entries.
    """
    numbered = {}
    for s in sources:
        m = re.match(r"Quelle\s*(\d+)[.:]?\s*(.*)", s)
        if m:
            numbered[int(m.group(1))] = m.group(2).strip()
        else:
            # Un-numbered source — append to end
            pass
    return numbered


def build_quellen_section(sources: list, cached: list) -> tuple:
    """
    Build a ## Quellen markdown section with sequential footnotes.
    Returns (quellen_text, old_to_new_map) where old_to_new_map remaps
    original source numbers (e.g. {1:1, 2:2, 4:3, 5:4}) so inline [n]
    refs can be rewritten to match the new sequential numbering.
    """
    numbered = extract_numbered_sources(sources)
    if not numbered:
        return "", {}

    old_to_new = {}
    lines = ["\n\n## Quellen\n"]
    for new_n, old_n in enumerate(sorted(numbered.keys()), 1):
        old_to_new[old_n] = new_n
        raw_name = numbered[old_n]
        url, _ = match_source_to_url(raw_name, cached)

        display = raw_name
        if url:
            lines.append(f"{new_n}. {display}. [{url}]({url}). Abgerufen am {TODAY}")
        else:
            lines.append(f"{new_n}. {display}")

    return "\n".join(lines) + "\n", old_to_new


def rewrite_inline_refs(body: str, old_to_new: dict) -> str:
    """Replace [old_n] citation refs with [new_n] to match sequential footnotes."""
    if not old_to_new:
        return body
    def replace_ref(m):
        n = int(m.group(1))
        return f"[{old_to_new.get(n, n)}]"
    # Only replace [n] that are citation refs (not wikilinks [[...]])
    return re.sub(r"(?<!\[)\[(\d+)\](?!\])", replace_ref, body)


def process_article(md_path: Path, dry_run: bool = False) -> bool:
    text = md_path.read_text(encoding="utf-8")
    meta_text, body = parse_frontmatter(text)

    if meta_text is None:
        return False

    import yaml
    try:
        meta = yaml.safe_load(meta_text)
    except Exception:
        return False

    sources = meta.get("sources", [])
    if not sources:
        return False

    # Only process if there are [n] markers in the body
    if not re.search(r"(?<!\[)\[\d+\](?!\])", body):
        return False

    title = meta.get("title", md_path.stem)
    cached = find_cached_results(title)

    if not cached:
        return False

    # Strip existing ## Quellen section from body
    body_clean = re.sub(r"\n## Quellen\b[\s\S]*$", "", body)

    quellen, old_to_new = build_quellen_section(sources, cached)
    if not quellen.strip():
        return False

    # Rewrite [n] refs to sequential numbering
    body_rewritten = rewrite_inline_refs(body_clean, old_to_new)

    new_body = body_rewritten.rstrip() + quellen
    new_text = "---" + meta_text + "---" + new_body

    if new_text == text:
        return False

    if not dry_run:
        md_path.write_text(new_text, encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cat", type=str, default=None)
    args = parser.parse_args()

    cats = [args.cat] if args.cat else CATEGORIES
    updated = 0
    total = 0

    for cat in cats:
        cat_dir = KNOWLEDGE_DIR / cat
        if not cat_dir.exists():
            continue
        for md_path in sorted(cat_dir.glob("*.md")):
            total += 1
            changed = process_article(md_path, dry_run=args.dry_run)
            if changed:
                updated += 1
                prefix = "[dry-run] " if args.dry_run else ""
                print(f"  {prefix}✓ {cat}/{md_path.stem}")

    verb = "würde aktualisieren" if args.dry_run else "aktualisiert"
    print(f"\n{updated}/{total} Artikel {verb}")


if __name__ == "__main__":
    main()
