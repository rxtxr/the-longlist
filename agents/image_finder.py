"""ImageFinder — finds real, licensed images from Wikimedia Commons for KB articles.

Searches Commons for the article subject, filters for usable licenses,
and returns image metadata (url, thumb, caption, license, source).
"""
import re
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
from typing import List, Dict, Optional


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
THUMB_WIDTH = 400

ALLOWED_LICENSES = {
    "public domain", "pd", "cc0", "cc-zero",
    "cc-by", "cc by", "creative commons",
    "cc-by-sa", "cc by-sa",
    "cc-by-2.0", "cc-by-3.0", "cc-by-4.0",
    "cc-by-sa-2.0", "cc-by-sa-3.0", "cc-by-sa-4.0",
}

# Exclude these image types (logos, user images, wiki infrastructure)
EXCLUDE_PATTERNS = [
    r"wiki.*(logo|icon|button|symbol)",
    r"^(flag|coat|emblem|seal)_of",
    r"commons.*logo",
    r"\.svg$",  # Skip SVG (usually logos/icons)
]


def _api_get(params: dict) -> Optional[dict]:
    params["format"] = "json"
    url = COMMONS_API + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "KBImageFinder/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _is_excluded(filename: str) -> bool:
    fname_lower = filename.lower()
    for pat in EXCLUDE_PATTERNS:
        if re.search(pat, fname_lower):
            return True
    return False


def _is_allowed_license(license_str: str) -> bool:
    low = license_str.lower()
    return any(lic in low for lic in ALLOWED_LICENSES)


def _get_image_info(titles: List[str]) -> List[Dict]:
    """Fetch image info (url, license, description) for a list of file titles."""
    if not titles:
        return []
    # Batch up to 10 at a time
    results = []
    for i in range(0, len(titles), 10):
        batch = titles[i:i+10]
        data = _api_get({
            "action": "query",
            "titles": "|".join(batch),
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size",
            "iiurlwidth": THUMB_WIDTH,
        })
        if not data:
            continue
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            info_list = page.get("imageinfo", [])
            if not info_list:
                continue
            info = info_list[0]
            meta = info.get("extmetadata", {})

            license_str = (
                meta.get("LicenseShortName", {}).get("value", "") or
                meta.get("License", {}).get("value", "")
            )
            if not _is_allowed_license(license_str):
                continue

            desc = (
                meta.get("ImageDescription", {}).get("value", "") or
                meta.get("ObjectName", {}).get("value", "")
            )
            # Strip HTML tags from description
            desc = re.sub(r"<[^>]+>", "", desc).strip()[:200]

            artist = meta.get("Artist", {}).get("value", "")
            artist = re.sub(r"<[^>]+>", "", artist).strip()[:100]

            thumb = info.get("thumburl", "")
            url = info.get("url", "")
            width = info.get("width", 0)
            height = info.get("height", 0)

            # Skip very small or very narrow images
            if width and height and (width < 100 or height < 100):
                continue

            if thumb and url:
                low_lic = license_str.lower()
                if any(x in low_lic for x in ("public domain", "pd", "cc0", "cc-zero")):
                    copyright_status = "public_domain"
                elif license_str:
                    copyright_status = "clear_cc"
                else:
                    copyright_status = "unknown"

                results.append({
                    "url": url,
                    "thumb_url": thumb or url,
                    "caption": desc[:150] if desc else page.get("title", "").replace("File:", ""),
                    "license": license_str or "© unbekannt",
                    "artist": artist or "unbekannt",
                    "source": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(page.get('title', ''))}",
                    "copyright_status": copyright_status,
                    "width": width,
                    "height": height,
                })
    return results


def search_commons(query: str, max_results: int = 5) -> List[Dict]:
    """Search Wikimedia Commons for images matching a query."""
    # Search for files
    data = _api_get({
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srnamespace": "6",  # File namespace
        "srlimit": max_results * 3,  # Request more to filter
    })
    if not data:
        return []

    hits = data.get("query", {}).get("search", [])
    titles = [h["title"] for h in hits if not _is_excluded(h["title"])]
    if not titles:
        return []

    images = _get_image_info(titles[:max_results * 2])
    return images[:max_results]


class ImageFinder:
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, slug: str) -> Optional[Path]:
        if self.cache_dir:
            return self.cache_dir / f"img_{slug}.json"
        return None

    def _cache_load(self, slug: str) -> Optional[List[Dict]]:
        p = self._cache_path(slug)
        if p and p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                pass
        return None

    def _cache_save(self, slug: str, images: List[Dict]):
        p = self._cache_path(slug)
        if p:
            p.write_text(json.dumps(images, ensure_ascii=False, indent=2))

    def find_images(self, title: str, category: str, max_images: int = 3) -> List[Dict]:
        """Find real images for a KB article. Returns list of image dicts."""
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower())[:40]
        cached = self._cache_load(slug)
        if cached is not None:
            return cached

        # Build targeted search queries
        short = re.split(r"\s[—–-]\s", title)[0].strip()
        short = re.sub(r"\s*\([^)]*\d{4}[^)]*\)", "", short).strip()

        queries = [short]
        if category == "agencies":
            queries += [f"{short} advertising agency"]
        elif category == "people":
            queries += [f"{short} portrait", f"{short} photographer"]
        elif category == "work":
            queries += [f"{short} advertisement", f"{short} campaign"]
        elif category == "eras":
            queries += [f"{short} advertising history"]

        seen_urls = set()
        images = []
        for q in queries:
            for img in search_commons(q, max_results=3):
                if img["url"] not in seen_urls:
                    seen_urls.add(img["url"])
                    images.append(img)
            if len(images) >= max_images:
                break
            time.sleep(0.2)

        images = images[:max_images]
        self._cache_save(slug, images)
        return images
