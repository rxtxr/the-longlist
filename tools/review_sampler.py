"""ReviewSampler — picks a representative cross-section of KB articles for review.

Selection strategy:
  - Stratified by category: agencies, people, work, eras + one minority category each
  - Stratified by confidence: high, medium, low represented
  - Include at least one article with many [ungesichert] markers (thin sources)
  - Include at least one with rich media
  - Total: ~12 articles (enough for pattern analysis, fits in context)
"""
import re
import random
from pathlib import Path
from typing import Dict, List

import frontmatter

from tools.knowledge_base import KnowledgeBase


SAMPLE_PLAN = [
    # (category, confidence, count)
    ("agencies",    "high",   2),
    ("agencies",    "medium", 1),
    ("agencies",    "low",    1),
    ("people",      "high",   1),
    ("people",      "medium", 1),
    ("people",      "low",    1),
    ("work",        "high",   1),
    ("work",        "low",    1),
    ("eras",        "medium", 1),
    ("philosophy",  None,     1),  # any confidence
    ("scandals",    None,     1),
]


class ReviewSampler:
    def __init__(self, kb: KnowledgeBase, seed: int = 42):
        self.kb = kb
        self.seed = seed

    def prepare(self) -> Dict:
        """Return dict: {corpus_stats: str, articles: [dict]}"""
        rng = random.Random(self.seed)
        pool = self._build_pool()
        articles = self._sample(pool, rng)
        return {
            "corpus_stats": self._corpus_stats(pool),
            "articles": articles,
        }

    def _build_pool(self) -> Dict:
        """Load all entries, grouped by (category, confidence)."""
        pool: Dict = {}
        for md in self.kb.root.rglob("*.md"):
            if md.parent.name == "visuals":
                continue
            try:
                e = frontmatter.load(str(md))
            except Exception:
                continue
            cat = md.parent.name
            conf = e.metadata.get("confidence", "low")
            key = (cat, conf)
            if key not in pool:
                pool[key] = []
            pool[key].append({
                "path": md,
                "title": e.metadata.get("title", md.stem),
                "category": cat,
                "confidence": conf,
                "content": e.content,
                "ungesichert": e.content.count("[ungesichert]"),
                "has_images": bool(e.metadata.get("images")),
                "sources": e.metadata.get("sources", []),
                "tags": e.metadata.get("tags", []),
            })
        return pool

    def _sample(self, pool: Dict, rng: random.Random) -> List[Dict]:
        selected = []
        seen_paths = set()

        for cat, conf, count in SAMPLE_PLAN:
            # Build candidate list
            if conf:
                candidates = pool.get((cat, conf), [])
            else:
                # Any confidence — merge all for that category
                candidates = []
                for c in ("high", "medium", "low"):
                    candidates += pool.get((cat, c), [])

            # Prefer articles with interesting [ungesichert] density (not 0, not absurd)
            scored = sorted(candidates, key=lambda a: (
                0 if 2 <= a["ungesichert"] <= 10 else 1,
                -len(a["content"]),
            ))
            picks = []
            for a in scored:
                if a["path"] not in seen_paths and len(picks) < count:
                    picks.append(a)
                    seen_paths.add(a["path"])
            selected.extend(picks)

        # Always include the one with the most [ungesichert] markers if not already in
        all_entries = [a for lst in pool.values() for a in lst]
        most_uncertain = max(all_entries, key=lambda a: a["ungesichert"])
        if most_uncertain["path"] not in seen_paths:
            most_uncertain["_note"] = "höchste [ungesichert]-Dichte im Korpus"
            selected.append(most_uncertain)

        return selected

    def _corpus_stats(self, pool: Dict) -> str:
        all_entries = [a for lst in pool.values() for a in lst]
        total = len(all_entries)

        by_cat = {}
        for a in all_entries:
            by_cat[a["category"]] = by_cat.get(a["category"], 0) + 1

        conf_dist = {}
        for a in all_entries:
            conf_dist[a["confidence"]] = conf_dist.get(a["confidence"], 0) + 1

        uc = [a["ungesichert"] for a in all_entries]
        avg_uc = sum(uc) / len(uc) if uc else 0
        has_img = sum(1 for a in all_entries if a["has_images"])

        cat_str = ", ".join(f"{k} ({v})" for k, v in sorted(by_cat.items(), key=lambda x: -x[1]))
        conf_str = " | ".join(
            f"{k}: {v} ({v*100//total}%)" for k, v in
            sorted(conf_dist.items(), key=lambda x: ["high","medium","low"].index(x[0]) if x[0] in ["high","medium","low"] else 9)
        )

        return (
            f"Gesamt: {total} Einträge\n"
            f"Kategorien: {cat_str}\n"
            f"Konfidenz: {conf_str}\n"
            f"Ø [ungesichert] pro Artikel: {avg_uc:.1f} (max: {max(uc)})\n"
            f"Mit Bildmaterial: {has_img} ({has_img*100//total}%)\n"
            f"Strukturschema: ## Überblick / ## Historischer Kontext / "
            f"## Wichtige Details / ## Bedeutung & Einfluss / ## Verbindungen / ## Bildmaterial-Hinweise"
        )
