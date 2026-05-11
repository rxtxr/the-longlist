"""Persistent knowledge base — read/write/search markdown entries with YAML frontmatter."""
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

import frontmatter
import yaml

from config import CATEGORIES, KNOWLEDGE_DIR, WIKI_OBSIDIAN_DIR


class KnowledgeBase:
    def __init__(self, root: Optional[Path] = None, obsidian_dir: Optional[Path] = None):
        self.root = root or KNOWLEDGE_DIR
        self.obsidian_dir = obsidian_dir or WIKI_OBSIDIAN_DIR
        self._ensure_dirs()

    def _ensure_dirs(self):
        self.root.mkdir(parents=True, exist_ok=True)
        for cat in CATEGORIES:
            (self.root / cat).mkdir(exist_ok=True)
        if self.obsidian_dir:
            self.obsidian_dir.mkdir(parents=True, exist_ok=True)
            for cat in CATEGORIES:
                (self.obsidian_dir / cat).mkdir(exist_ok=True)

    @staticmethod
    def slug(text: str) -> str:
        s = text.lower()
        s = re.sub(r"[äÄ]", "ae", s)
        s = re.sub(r"[öÖ]", "oe", s)
        s = re.sub(r"[üÜ]", "ue", s)
        s = re.sub(r"[ß]", "ss", s)
        s = re.sub(r"[^a-z0-9_]+", "_", s)
        return s.strip("_")[:80]

    def path_for(self, category: str, entry_id: str) -> Path:
        return self.root / category / f"{self.slug(entry_id)}.md"

    def write_entry(
        self,
        category: str,
        entry_id: str,
        title: str,
        content: str,
        metadata: Dict[str, Any],
        wave: int,
    ) -> Path:
        """Write (or overwrite) a knowledge entry. Returns the file path."""
        if category not in CATEGORIES:
            category = "agencies"

        path = self.path_for(category, entry_id)

        # Preserve existing wave + any extra fields (e.g. images) if re-writing
        existing_wave = wave
        extra_preserved = {}
        _PRESERVED_EXTRA = {"images", "strict_verified_wave", "relevance_wave",
                            "ungesichert", "corrected", "verified"}
        if path.exists():
            try:
                old = frontmatter.load(str(path))
                existing_wave = old.metadata.get("wave", wave)
                for k in _PRESERVED_EXTRA:
                    if k in old.metadata:
                        extra_preserved[k] = old.metadata[k]
            except Exception:
                pass

        meta = {
            "id":           self.slug(entry_id),
            "type":         category.rstrip("s"),
            "title":        title,
            "tags":         metadata.get("tags", []),
            "era":          metadata.get("era", ""),
            "related":      metadata.get("related", []),
            "sources":      metadata.get("sources", []),
            "confidence":   metadata.get("confidence", "medium"),
            "wave":         existing_wave,
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            **extra_preserved,
        }

        post = frontmatter.Post(content.strip(), **meta)
        text = frontmatter.dumps(post)
        path.write_text(text, encoding="utf-8")

        # Mirror to Obsidian vault immediately
        self._write_obsidian(category, entry_id, title, content, meta)

        return path

    def _write_obsidian(self, category: str, entry_id: str, title: str,
                        content: str, meta: Dict[str, Any]):
        """Write Obsidian-compatible markdown with [[wikilinks]] to the vault."""
        if not self.obsidian_dir:
            return
        try:
            obs_dir = self.obsidian_dir / category
            obs_dir.mkdir(parents=True, exist_ok=True)
            fname = f"{self.slug(entry_id)}.md"

            tags = meta.get("tags", [])
            era = meta.get("era", "")
            fm_lines = [
                "---",
                f'title: "{title}"',
                f"type: {category}",
                f'era: "{era}"',
                f"tags: [{', '.join(str(t) for t in tags)}]",
                f"confidence: {meta.get('confidence', 'medium')}",
                f"wave: {meta.get('wave', 0)}",
                f"last_updated: {meta.get('last_updated', '')}",
                "---",
                "",
            ]
            (obs_dir / fname).write_text(
                "\n".join(fm_lines) + f"# {title}\n\n" + content.strip(),
                encoding="utf-8",
            )
        except Exception as e:
            pass  # Never block research on Obsidian write errors

    def read_entry(self, path: Path) -> Optional[Dict]:
        try:
            post = frontmatter.load(str(path))
            return {
                "meta":    post.metadata,
                "content": post.content,
                "path":    path,
            }
        except Exception:
            return None

    def get(self, category: str, entry_id: str) -> Optional[Dict]:
        path = self.path_for(category, entry_id)
        return self.read_entry(path) if path.exists() else None

    def exists(self, category: str, entry_id: str) -> bool:
        return self.path_for(category, entry_id).exists()

    def list_category(self, category: str) -> List[Dict]:
        cat_dir = self.root / category
        if not cat_dir.exists():
            return []
        entries = []
        for f in sorted(cat_dir.glob("*.md")):
            e = self.read_entry(f)
            if e:
                entries.append(e)
        return entries

    def list_all(self) -> List[Dict]:
        entries = []
        for cat in CATEGORIES:
            entries.extend(self.list_category(cat))
        return entries

    def search(self, query: str, category: Optional[str] = None) -> List[Dict]:
        q = query.lower()
        dirs = [self.root / category] if category else [
            self.root / cat for cat in CATEGORIES
        ]
        results = []
        for d in dirs:
            if not d.exists():
                continue
            for f in d.glob("*.md"):
                e = self.read_entry(f)
                if not e:
                    continue
                haystack = (
                    e["content"].lower()
                    + str(e["meta"].get("tags", "")).lower()
                    + e["meta"].get("title", "").lower()
                )
                if q in haystack:
                    results.append(e)
        return results

    def get_stats(self) -> Dict[str, int]:
        stats: Dict[str, int] = {}
        for cat in CATEGORIES:
            cat_dir = self.root / cat
            stats[cat] = len(list(cat_dir.glob("*.md"))) if cat_dir.exists() else 0
        stats["total"] = sum(stats.values())
        return stats

    def all_tags(self) -> Dict[str, int]:
        tag_count: Dict[str, int] = {}
        for e in self.list_all():
            for tag in e["meta"].get("tags", []):
                tag_count[tag] = tag_count.get(tag, 0) + 1
        return dict(sorted(tag_count.items(), key=lambda x: -x[1]))
