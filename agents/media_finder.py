"""MediaFinder — finds real media (images + videos) from multiple open sources.

Sources:
  1. Wikimedia Commons  — CC/PD images
  2. OpenVerse          — aggregates Flickr Commons, Europeana, Smithsonian, etc.
  3. YouTube            — via yt-dlp (vintage ads, interviews, documentaries)

Every item carries full attribution: source, license, artist, copyright_status.
Unknown copyright is explicitly flagged.
"""
import re
import json
import time
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from typing import List, Dict, Optional


# ── Wikimedia Commons ────────────────────────────────────────────────────────

COMMONS_API  = "https://commons.wikimedia.org/w/api.php"
THUMB_WIDTH  = 400

ALLOWED_LICENSES = {
    "public domain", "pd", "cc0", "cc-zero",
    "cc-by", "cc by", "creative commons",
    "cc-by-sa", "cc by-sa",
    "cc-by-2.0", "cc-by-3.0", "cc-by-4.0",
    "cc-by-sa-2.0", "cc-by-sa-3.0", "cc-by-sa-4.0",
}

EXCLUDE_PATTERNS = [
    r"wiki.*(logo|icon|button|symbol)",
    r"^(flag|coat|emblem|seal)_of",
    r"commons.*logo",
    r"\.svg$",
]


def _is_excluded(filename: str) -> bool:
    fl = filename.lower()
    return any(re.search(p, fl) for p in EXCLUDE_PATTERNS)


def _is_allowed_license(lic: str) -> bool:
    low = lic.lower()
    return any(a in low for a in ALLOWED_LICENSES)


def _copyright_status(lic: str) -> str:
    low = lic.lower()
    if any(x in low for x in ("public domain", "pd", "cc0", "cc-zero")):
        return "public_domain"
    if lic:
        return "clear_cc"
    return "unknown"


def _api_get(url: str, params: dict) -> Optional[dict]:
    params["format"] = "json"
    full = url + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(full, headers={"User-Agent": "TheLonglist/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _commons_search(query: str, max_results: int = 5) -> List[Dict]:
    data = _api_get(COMMONS_API, {
        "action": "query", "list": "search",
        "srsearch": query, "srnamespace": "6",
        "srlimit": max_results * 3,
    })
    if not data:
        return []
    hits = data.get("query", {}).get("search", [])
    titles = [h["title"] for h in hits if not _is_excluded(h["title"])]
    if not titles:
        return []

    results = []
    for i in range(0, min(len(titles), max_results * 2), 10):
        batch = titles[i:i+10]
        info_data = _api_get(COMMONS_API, {
            "action": "query", "titles": "|".join(batch),
            "prop": "imageinfo", "iiprop": "url|extmetadata|size",
            "iiurlwidth": THUMB_WIDTH,
        })
        if not info_data:
            continue
        for page in info_data.get("query", {}).get("pages", {}).values():
            il = page.get("imageinfo", [])
            if not il:
                continue
            info = il[0]
            meta = info.get("extmetadata", {})
            lic = (meta.get("LicenseShortName", {}).get("value", "") or
                   meta.get("License", {}).get("value", ""))
            if not _is_allowed_license(lic):
                continue
            desc = re.sub(r"<[^>]+>", "",
                          meta.get("ImageDescription", {}).get("value", "") or
                          meta.get("ObjectName", {}).get("value", "")).strip()[:200]
            artist = re.sub(r"<[^>]+>", "",
                            meta.get("Artist", {}).get("value", "")).strip()[:100]
            thumb = info.get("thumburl", "")
            url   = info.get("url", "")
            w, h  = info.get("width", 0), info.get("height", 0)
            if w and h and (w < 100 or h < 100):
                continue
            if thumb and url:
                results.append({
                    "type": "image",
                    "url": url,
                    "thumb_url": thumb,
                    "caption": desc[:150] or page.get("title", "").replace("File:", ""),
                    "license": lic or "© unbekannt",
                    "artist": artist or "unbekannt",
                    "source_url": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(page.get('title', ''))}",
                    "source_label": "Wikimedia Commons",
                    "copyright_status": _copyright_status(lic),
                    "width": w, "height": h,
                })
    return results[:max_results]


# ── OpenVerse ────────────────────────────────────────────────────────────────

OPENVERSE_API = "https://api.openverse.org/v1/images/"

_OV_LICENSE_MAP = {
    "cc0": "public_domain", "pdm": "public_domain",
    "by": "clear_cc", "by-sa": "clear_cc",
    "by-nc": "clear_cc", "by-nd": "clear_cc",
    "by-nc-sa": "clear_cc", "by-nc-nd": "clear_cc",
}


def _openverse_search(query: str, max_results: int = 4) -> List[Dict]:
    try:
        params = urllib.parse.urlencode({
            "q": query, "page_size": max_results * 2,
        })
        req = urllib.request.Request(
            f"{OPENVERSE_API}?{params}",
            headers={"User-Agent": "TheLonglist/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return []

    results = []
    for item in data.get("results", []):
        thumb = item.get("thumbnail", "")
        url   = item.get("url", "") or item.get("foreign_landing_url", "")
        if not thumb or not url:
            continue
        lic_slug = item.get("license", "").lower()
        lic_ver  = item.get("license_version", "")
        lic_str  = f"CC {lic_slug.upper()} {lic_ver}".strip() if lic_slug not in ("cc0", "pdm") else (
            "CC0 1.0" if lic_slug == "cc0" else "Public Domain Mark"
        )
        status = _OV_LICENSE_MAP.get(lic_slug, "unknown")
        creator = item.get("creator", "") or "unbekannt"
        source  = item.get("source", "")
        results.append({
            "type": "image",
            "url": url,
            "thumb_url": thumb,
            "caption": (item.get("title", "") or "")[:150],
            "license": lic_str,
            "artist": creator[:100],
            "source_url": item.get("foreign_landing_url", url),
            "source_label": f"OpenVerse / {source}",
            "copyright_status": status,
            "width": item.get("width", 0),
            "height": item.get("height", 0),
        })
    return results[:max_results]


# ── YouTube ──────────────────────────────────────────────────────────────────

def _youtube_search(query: str, max_results: int = 2) -> List[Dict]:
    """Search YouTube via yt-dlp. Returns video metadata for embedding."""
    try:
        cmd = [
            "yt-dlp", "--flat-playlist", "--no-warnings",
            "--print", "%(id)s|||%(title)s|||%(duration)s",
            f"ytsearch{max_results * 2}:{query}",
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        lines = [l.strip() for l in out.stdout.strip().splitlines() if "|||" in l]
    except Exception:
        return []

    results = []
    for line in lines[:max_results]:
        parts = line.split("|||")
        if len(parts) < 2:
            continue
        vid_id = parts[0].strip()
        title  = parts[1].strip()
        dur    = float(parts[2]) if len(parts) > 2 and parts[2].strip() else 0

        # Skip very short (<30s) or very long (>60min) videos
        if dur and (dur < 30 or dur > 3600):
            continue

        dur_str = f"{int(dur//60)}:{int(dur%60):02d}" if dur else ""

        results.append({
            "type": "video",
            "platform": "youtube",
            "video_id": vid_id,
            "embed_url": f"https://www.youtube-nocookie.com/embed/{vid_id}",
            "thumb_url": f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg",
            "url": f"https://www.youtube.com/watch?v={vid_id}",
            "caption": title,
            "duration": dur_str,
            "license": "YouTube Standard License",
            "artist": "",
            "source_url": f"https://www.youtube.com/watch?v={vid_id}",
            "source_label": "YouTube",
            "copyright_status": "youtube",
        })
    return results


# ── MediaFinder ──────────────────────────────────────────────────────────────

class MediaFinder:
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, slug: str) -> Optional[Path]:
        return (self.cache_dir / f"media_{slug}.json") if self.cache_dir else None

    def _cache_load(self, slug: str) -> Optional[List[Dict]]:
        p = self._cache_path(slug)
        if p and p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                pass
        return None

    def _cache_save(self, slug: str, items: List[Dict]):
        p = self._cache_path(slug)
        if p:
            p.write_text(json.dumps(items, ensure_ascii=False, indent=2))

    def find_media(self, title: str, category: str,
                   max_images: int = 2, max_videos: int = 2,
                   meta: Optional[dict] = None) -> List[Dict]:
        """Find images and videos for a KB article. Returns combined media list."""
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower())[:40]
        cached = self._cache_load(slug)
        if cached is not None:
            return cached

        short = re.split(r"\s[—–-]\s", title)[0].strip()
        short = re.sub(r"\s*\([^)]*\d{4}[^)]*\)", "", short).strip()
        tags  = (meta or {}).get("tags", [])
        era   = (meta or {}).get("era", "")

        image_queries, video_queries = self._build_queries(
            short, title, category, tags, era
        )

        # ── Images: Commons first, OpenVerse as fallback ──
        seen_urls: set = set()
        images: List[Dict] = []

        for q in image_queries:
            if len(images) >= max_images:
                break
            for img in _commons_search(q, max_results=max_images):
                if img["url"] not in seen_urls:
                    seen_urls.add(img["url"])
                    images.append(img)
            time.sleep(0.1)

        if len(images) < max_images:
            for q in image_queries[:2]:
                if len(images) >= max_images:
                    break
                for img in _openverse_search(q, max_results=max_images):
                    if img["url"] not in seen_urls:
                        seen_urls.add(img["url"])
                        images.append(img)
                time.sleep(0.1)

        images = images[:max_images]

        # ── Videos: YouTube ──
        videos: List[Dict] = []
        seen_vids: set = set()
        for q in video_queries:
            if len(videos) >= max_videos:
                break
            for v in _youtube_search(q, max_results=max_videos):
                if v["video_id"] not in seen_vids:
                    seen_vids.add(v["video_id"])
                    videos.append(v)
            time.sleep(0.15)
        videos = videos[:max_videos]

        result = images + videos
        self._cache_save(slug, result)
        return result

    def _build_queries(self, short: str, title: str, category: str,
                       tags: list, era: str):
        """Returns (image_queries, video_queries) tuples."""
        img_q: List[str] = []
        vid_q: List[str] = []

        if category == "people":
            img_q = [f"{short} portrait", short, f"{short} advertising"]
            vid_q = [
                f"{short} advertising interview",
                f"{short} documentary advertising",
                f"{short} speech talk",
            ]
        elif category == "agencies":
            founders = [t.replace("_", " ") for t in tags
                        if len(t) > 4 and "_" in t][:2]
            img_q = [short] + [f"{f} portrait" for f in founders] + [f"{short} building"]
            vid_q = [
                f"{short} advertising agency history",
                f"{short} campaign documentary",
            ]
        elif category == "work":
            img_q = [short, f"{short} advertisement poster", f"{short} campaign"]
            vid_q = [
                f"{short} original commercial ad",
                f"{short} advertisement television",
            ]
        elif category == "eras":
            decade = re.search(r"(\d{4})", era or title)
            dec_str = decade.group(1)[:3] + "0s" if decade else ""
            img_q = [f"{short} advertising", f"{dec_str} advertising history" if dec_str else short]
            vid_q = [
                f"{dec_str} advertising classic commercials" if dec_str else f"{short} advertising history",
                f"history of advertising {dec_str}" if dec_str else short,
            ]
        elif category == "scandals":
            img_q = [short, f"{short} advertising"]
            vid_q = [f"{short} advertising controversy", f"{short} scandal documentary"]
        elif category == "technology":
            img_q = [short, f"{short} office equipment vintage"]
            vid_q = [f"{short} advertising history", f"{short} how it works"]
        elif category == "philosophy":
            img_q = [short, f"{short} advertising concept"]
            vid_q = [f"{short} advertising theory", f"{short} marketing documentary"]
        elif category == "life":
            img_q = [short, f"{short} advertising agency"]
            vid_q = [f"{short} advertising agency life documentary"]
        else:
            img_q = [short]
            vid_q = [f"{short} advertising"]

        if short not in img_q:
            img_q.append(short)

        return img_q, vid_q
