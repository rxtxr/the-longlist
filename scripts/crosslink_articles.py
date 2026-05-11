"""
Crosslink articles: scan each article for mentions of other KB entry titles
that are not already [[wikilinked]], and add the missing [[Title]] markup.

Usage:
  python scripts/crosslink_articles.py           # all articles
  python scripts/crosslink_articles.py --dry-run # preview only
  python scripts/crosslink_articles.py --cat agencies
"""
import re
import argparse
from pathlib import Path
from typing import Dict, List, Tuple

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"
CATEGORIES = ["agencies", "people", "eras", "work", "scandals", "technology", "life", "philosophy"]

# Don't link these — too generic, would spam links
SKIP_TITLES = {
    "new york", "london", "usa", "usa.", "the", "in", "an", "und", "die", "der",
    "das", "von", "mit", "für", "auf", "aus", "bei", "als",
}

MIN_TITLE_LEN = 4  # don't link very short names


def _title_short(title: str) -> str:
    """Get the primary short form of a title (before first dash/em-dash)."""
    short = re.split(r"\s[—–-]\s", title)[0].strip()
    short = re.sub(r"\s*\([^)]*\)", "", short).strip()
    return short


def build_title_index(exclude_path: Path = None) -> List[Tuple[str, str]]:
    """
    Build sorted list of (display_name, pattern_string) for all KB entries.
    Sorted longest-first so more specific matches take priority.
    exclude_path: skip this file's own entry to avoid self-linking.
    """
    entries = []  # (display_title, short_name, full_title)
    for cat in CATEGORIES:
        cat_dir = KNOWLEDGE_DIR / cat
        if not cat_dir.exists():
            continue
        for md_path in cat_dir.glob("*.md"):
            if exclude_path and md_path == exclude_path:
                continue
            text = md_path.read_text(encoding="utf-8")
            # Extract title from frontmatter
            title = ""
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 2:
                    import yaml
                    try:
                        meta = yaml.safe_load(parts[1])
                        title = meta.get("title", "")
                    except Exception:
                        pass
            if not title:
                title = md_path.stem.replace("_", " ").title()

            short = _title_short(title)

            # Collect all linkable name variants
            for name in {title, short}:
                name = name.strip()
                if len(name) >= MIN_TITLE_LEN and name.lower() not in SKIP_TITLES:
                    entries.append((name, title))  # (variant_to_match, canonical_title)

    # Deduplicate, longest first
    seen = set()
    unique = []
    for variant, canonical in sorted(entries, key=lambda x: -len(x[0])):
        if variant not in seen:
            seen.add(variant)
            unique.append((variant, canonical))
    return unique


def _is_in_wikilink(pos: int, text: str) -> bool:
    """Check if position is already inside [[...]] or a markdown link [...](...) or header."""
    # Check if inside [[...]]
    before = text[:pos]
    bracket_open = before.rfind("[[")
    bracket_close = before.rfind("]]")
    if bracket_open > bracket_close:
        return True
    # Check if inside [...](...) markdown link text
    link_open = before.rfind("[")
    link_close = before.rfind("]")
    if link_open > link_close:
        # Check if it looks like a markdown link (followed by (...))
        after = text[pos:]
        if re.match(r".*?\]\(", after[:200]):
            return True
    # Check if on a header line
    line_start = before.rfind("\n") + 1
    if text[line_start:line_start+2] in ("##", "# "):
        return True
    return False


def _is_in_frontmatter(pos: int, text: str) -> bool:
    """Check if position is in YAML frontmatter (before second ---)."""
    if not text.startswith("---"):
        return False
    second = text.find("---", 3)
    return second >= 0 and pos < second


def add_crosslinks(md_path: Path, title_index: List[Tuple[str, str]], dry_run: bool = False) -> int:
    """
    Add [[wikilinks]] for unlinked mentions. Returns number of links added.
    """
    text = md_path.read_text(encoding="utf-8")

    # Split off frontmatter — only work on body
    frontmatter = ""
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            frontmatter = "---" + parts[1] + "---"
            body = parts[2]

    links_added = 0
    modified_body = body

    for variant, canonical in title_index:
        # Skip if variant already appears as [[variant]] or [[canonical]]
        already_linked = bool(
            re.search(re.escape(f"[[{variant}]]"), modified_body) or
            re.search(re.escape(f"[[{canonical}]]"), modified_body)
        )
        if already_linked:
            continue

        # Find all occurrences in the body (word-boundary match, case-sensitive for proper nouns)
        # Use word boundary but allow for trailing punctuation
        pattern = r"(?<!\[)(?<!\[\[)" + re.escape(variant) + r"(?!\])"

        new_body = ""
        last_end = 0
        replaced_once = False  # only link the first occurrence per article

        for m in re.finditer(pattern, modified_body):
            start, end = m.start(), m.end()
            # Skip if in frontmatter context or already linked context
            if _is_in_frontmatter(start, text) or _is_in_wikilink(start, modified_body):
                new_body += modified_body[last_end:end]
                last_end = end
                continue
            # Only replace first occurrence
            if replaced_once:
                new_body += modified_body[last_end:end]
                last_end = end
                continue
            # Add the wikilink
            new_body += modified_body[last_end:start]
            new_body += f"[[{canonical}]]" if canonical != variant else f"[[{variant}]]"
            last_end = end
            replaced_once = True
            links_added += 1

        new_body += modified_body[last_end:]
        modified_body = new_body

    if links_added > 0 and not dry_run:
        md_path.write_text(frontmatter + modified_body, encoding="utf-8")

    return links_added


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cat", type=str, default=None)
    args = parser.parse_args()

    cats = [args.cat] if args.cat else CATEGORIES
    total_links = 0
    changed_files = 0

    for cat in cats:
        cat_dir = KNOWLEDGE_DIR / cat
        if not cat_dir.exists():
            continue
        for md_path in sorted(cat_dir.glob("*.md")):
            # Build index excluding current file (no self-links)
            index = build_title_index(exclude_path=md_path)
            count = add_crosslinks(md_path, index, dry_run=args.dry_run)
            if count > 0:
                changed_files += 1
                total_links += count
                prefix = "[dry-run] " if args.dry_run else ""
                print(f"  {prefix}+{count} Links: {cat}/{md_path.stem}")

    verb = "würden" if args.dry_run else "wurden"
    print(f"\n{total_links} Links {verb} in {changed_files} Artikeln hinzugefügt")


if __name__ == "__main__":
    main()
