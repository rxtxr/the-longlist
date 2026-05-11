"""
Find and optionally merge duplicate KB articles.

Duplicates are detected by:
  1. Near-identical titles (after slug normalization)
  2. High word-overlap between article bodies (Jaccard >= 0.6)

Usage:
  python scripts/find_duplicates.py            # list duplicates
  python scripts/find_duplicates.py --merge    # merge automatically (keeps longer article)
  python scripts/find_duplicates.py --cat agencies
"""
import re
import argparse
import yaml
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"
CATEGORIES = ["agencies", "people", "eras", "work", "scandals", "technology", "life", "philosophy", "visuals"]

JACCARD_THRESHOLD = 0.60
TITLE_SIM_THRESHOLD = 0.75


def _slug(text: str) -> str:
    s = text.lower()
    for old, new in [("ä","ae"),("ö","oe"),("ü","ue"),("ß","ss")]:
        s = s.replace(old, new)
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def _title_core(title: str) -> str:
    """Strip subtitle, year ranges, parentheticals."""
    t = re.split(r"\s[—–-]\s", title)[0].strip()
    t = re.sub(r"\s*\([^)]*\)", "", t).strip()
    return t.lower()


def _words(text: str) -> set:
    return set(re.findall(r"\w{4,}", text.lower()))


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _title_sim(a: str, b: str) -> float:
    wa = set(re.findall(r"\w{3,}", _title_core(a)))
    wb = set(re.findall(r"\w{3,}", _title_core(b)))
    return _jaccard(wa, wb)


def load_entries(cats):
    entries = []
    for cat in cats:
        cat_dir = KNOWLEDGE_DIR / cat
        if not cat_dir.exists():
            continue
        for md_path in sorted(cat_dir.glob("*.md")):
            text = md_path.read_text(encoding="utf-8")
            meta, body = {}, text
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    try:
                        meta = yaml.safe_load(parts[1]) or {}
                    except Exception:
                        pass
                    body = parts[2]
            title = meta.get("title", md_path.stem.replace("_", " ").title())
            entries.append({
                "path": md_path,
                "cat": cat,
                "title": title,
                "meta": meta,
                "body": body,
                "words": _words(body),
            })
    return entries


def find_duplicates(entries, threshold: float = JACCARD_THRESHOLD):
    pairs = []
    for i, a in enumerate(entries):
        for b in entries[i+1:]:
            # Must be same category
            if a["cat"] != b["cat"]:
                continue
            tsim = _title_sim(a["title"], b["title"])
            if tsim >= TITLE_SIM_THRESHOLD:
                jsim = _jaccard(a["words"], b["words"])
                pairs.append((tsim, jsim, a, b))
                continue
            # Also check high body overlap even with different titles
            jsim = _jaccard(a["words"], b["words"])
            if jsim >= threshold:
                pairs.append((tsim, jsim, a, b))

    pairs.sort(key=lambda x: -(x[0] + x[1]))
    return pairs


def merge_pair(a, b, dry_run: bool):
    """Keep the longer article, append unique sources from the shorter one."""
    keep, drop = (a, b) if len(a["body"]) >= len(b["body"]) else (b, a)

    # Merge sources lists
    keep_sources = keep["meta"].get("sources", [])
    drop_sources = drop["meta"].get("sources", [])
    merged_sources = list(keep_sources)
    for s in drop_sources:
        if s not in merged_sources:
            merged_sources.append(s)

    # Merge tags
    keep_tags = set(keep["meta"].get("tags", []))
    drop_tags = set(drop["meta"].get("tags", []))
    merged_tags = sorted(keep_tags | drop_tags)

    updated_meta = dict(keep["meta"])
    if merged_sources:
        updated_meta["sources"] = merged_sources
    if merged_tags:
        updated_meta["tags"] = merged_tags

    if not dry_run:
        # Rewrite keep file with merged metadata
        meta_yaml = yaml.dump(updated_meta, allow_unicode=True, default_flow_style=False, sort_keys=True)
        keep["path"].write_text(f"---\n{meta_yaml}---{keep['body']}", encoding="utf-8")
        # Delete the shorter duplicate
        drop["path"].unlink()

    return keep["path"], drop["path"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--merge", action="store_true", help="Automatically merge duplicates")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--cat", type=str, default=None)
    parser.add_argument("--threshold", type=float, default=JACCARD_THRESHOLD,
                        help=f"Jaccard threshold (default {JACCARD_THRESHOLD})")
    args = parser.parse_args()

    threshold = args.threshold
    cats = [args.cat] if args.cat else CATEGORIES
    entries = load_entries(cats)
    pairs = find_duplicates(entries, threshold=threshold)

    if not pairs:
        print("Keine Dubletten gefunden.")
        return

    print(f"\n{len(pairs)} potenzielle Dubletten:\n")
    merged = 0
    for tsim, jsim, a, b in pairs:
        print(f"  [{a['cat']}] title={tsim:.2f} body={jsim:.2f}")
        print(f"    A: {a['title']}")
        print(f"       {a['path'].name}")
        print(f"    B: {b['title']}")
        print(f"       {b['path'].name}")

        if args.merge or args.dry_run:
            keep_path, drop_path = merge_pair(a, b, dry_run=args.dry_run)
            prefix = "[dry-run] " if args.dry_run else ""
            longer = "A" if a["path"] == keep_path else "B"
            print(f"    → {prefix}Behalte {longer}, lösche {'B' if longer == 'A' else 'A'}")
            if not args.dry_run:
                merged += 1
        print()

    if args.merge and not args.dry_run:
        print(f"{merged} Dubletten zusammengeführt.")
    elif args.dry_run:
        print(f"[dry-run] {len(pairs)} Dubletten würden zusammengeführt.")


if __name__ == "__main__":
    main()
