"""DuckDuckGo web search wrapper with structured result caching."""
import time
from typing import List, Dict, Optional
from pathlib import Path
import json

try:
    from ddgs import DDGS
    _DDGS_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        _DDGS_AVAILABLE = True
    except ImportError:
        _DDGS_AVAILABLE = False


class WebSearch:
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def search(self, query: str, max_results: int = 5,
               region: str = "de-de") -> List[Dict]:
        import re as _re
        cache_key = _re.sub(r"[^a-z0-9_]", "_", query.lower())[:80]
        if self.cache_dir:
            cache_file = self.cache_dir / f"{cache_key}.json"
            if cache_file.exists():
                return json.loads(cache_file.read_text())

        if not _DDGS_AVAILABLE:
            print("  [WebSearch] duckduckgo_search nicht installiert")
            return []

        results = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, region=region, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "href":  r.get("href", ""),
                        "body":  r.get("body", ""),
                    })
            time.sleep(0.5)
        except Exception as e:
            print(f"  [WebSearch] Fehler bei '{query}': {e}")

        if self.cache_dir and results:
            cache_file = self.cache_dir / f"{cache_key}.json"
            cache_file.write_text(json.dumps(results, ensure_ascii=False, indent=2))

        return results

    def search_images(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search for image references (titles + URLs only, no download)."""
        if not _DDGS_AVAILABLE:
            return []
        results = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.images(query, max_results=max_results):
                    results.append({
                        "title":     r.get("title", ""),
                        "url":       r.get("url", ""),
                        "thumbnail": r.get("thumbnail", ""),
                        "source":    r.get("source", ""),
                        "width":     r.get("width", 0),
                        "height":    r.get("height", 0),
                    })
            time.sleep(0.5)
        except Exception as e:
            print(f"  [WebSearch/Images] Fehler bei '{query}': {e}")
        return results
