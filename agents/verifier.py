"""Verifier — fact-checking agent. Verifies KB entries against web sources and rewrites hallucinated content."""
import re
import json
from pathlib import Path
from typing import Optional, Dict, List

from agents.base_agent import BaseAgent
from tools.knowledge_base import KnowledgeBase
from tools.web_search import WebSearch

_SYSTEM = """Du bist ein präziser Faktenprüfer für historische Texte über die Werbebranche.
Deine Aufgabe: Artikel über Werbeagenturen, Personen und Kampagnen auf Korrektheit prüfen.

Du erkennst:
- Falsche Jahreszahlen (z.B. Gründungsjahre, Kampagnendaten)
- Erfundene Zitate oder Anekdoten
- Verwechslungen von Personen oder Agenturen
- Übertreibungen oder unbegründete Behauptungen
- Halluzinierte Details ohne Quellengrundlage

Sei konservativ: Zweifle nur, wenn Du konkrete Widersprüche siehst.
Antworte auf Deutsch. Sei präzise."""

_VERIFY_PROMPT = """Überprüfe diesen Artikel auf sachliche Richtigkeit.

## Artikel: {title}

{content}

## Web-Quellen zur Verifizierung:
{web_context}

## Aufgabe:
1. Identifiziere konkrete Fehler oder Halluzinationen (Jahreszahlen, Namen, Fakten)
2. Wenn Fehler gefunden: Schreibe den KOMPLETTEN Artikel neu, korrigiert und belegt
3. Wenn kein gravierender Fehler: Antworte nur mit "OK"

Wenn du neu schreibst, behalte exakt die gleiche Struktur:
## Überblick
## Historischer Kontext
## Wichtige Details
## Bedeutung & Einfluss
## Verbindungen
## Bildmaterial-Hinweise

Schreibe am Ende (nur bei Korrekturen):
## Korrekturen
- Was wurde korrigiert und warum

## Quellen
```json
["Quelle 1 (URL oder Titel)", "Quelle 2", ...]
```"""


class Verifier(BaseAgent):
    name = "verifier"
    model_key = "verifier"
    system_prompt = _SYSTEM

    def __init__(self, kb: KnowledgeBase):
        super().__init__()
        self.kb = kb
        self.search = WebSearch(
            cache_dir=kb.root.parent / "waves" / "_search_cache"
        )

    def verify_entry(self, entry: Dict, wave: int) -> bool:
        """Verify one KB entry. Returns True if article was corrected."""
        meta = entry["meta"]
        content = entry["content"]
        title = meta.get("title", entry["path"].stem)
        category = entry["path"].parent.name

        # Skip visual entries — they're image research notes, not factual articles
        if category == "visuals":
            return False

        print(f"  [Verifier] Prüfe: {title[:60]}")

        # Web search for the topic
        query = f"{title} advertising agency history facts"
        results = self.search.search(query, max_results=5)
        if not results:
            # Try German query
            results = self.search.search(
                f"Werbeagentur {title} Geschichte Fakten", max_results=4
            )

        if not results:
            print(f"  [Verifier]   → keine Web-Quellen, übersprungen")
            return False

        web_context = "\n".join(
            f"[{r['title']}] {r['body'][:500]}"
            for r in results[:4]
        )

        prompt = _VERIFY_PROMPT.format(
            title=title,
            content=content[:6000],  # Limit to avoid token overflow
            web_context=web_context,
        )

        raw = self.call(prompt, temperature=0.2, max_tokens=6000)

        if not raw or raw.strip().upper() == "OK" or raw.strip().startswith("OK"):
            print(f"  [Verifier]   ✓ Keine Fehler gefunden")
            return False

        # Extract corrections summary and sources
        corrections = _extract_section(raw, "Korrekturen")
        sources = _extract_sources(raw)
        new_content = _extract_article(raw)

        if not new_content or len(new_content) < 300:
            print(f"  [Verifier]   ✓ Keine verwertbare Korrektur")
            return False

        print(f"  [Verifier]   ✗ Korrekturen gefunden — schreibe neu")
        if corrections:
            for line in corrections.splitlines()[:3]:
                if line.strip():
                    print(f"  [Verifier]     {line.strip()[:80]}")

        # Build updated metadata
        updated_meta = dict(meta)
        updated_meta["verified_wave"] = wave
        updated_meta["confidence"] = "high"
        if sources:
            updated_meta["sources"] = sources

        self.kb.write_entry(
            category=category,
            entry_id=entry["path"].stem,
            title=title,
            content=new_content,
            metadata=updated_meta,
            wave=wave,
        )
        return True


def _extract_section(text: str, heading: str) -> str:
    match = re.search(rf"## {heading}\s*(.*?)(?=\n## |\Z)", text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_sources(text: str) -> List[str]:
    match = re.search(r"## Quellen\s*```json\s*(\[.*?\])\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return []


def _extract_article(text: str) -> str:
    # Remove correction/source sections at the end, keep the article body
    article = re.sub(r"\n## Korrekturen.*", "", text, flags=re.DOTALL)
    article = re.sub(r"\n## Quellen.*", "", article, flags=re.DOTALL)
    # Must start with ## Überblick
    match = re.search(r"(## Überblick.*)", article, re.DOTALL)
    if match:
        return match.group(1).strip()
    return article.strip()
