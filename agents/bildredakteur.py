"""Bildredakteur — visual research agent. Finds and contextualizes historical imagery."""
import re
import json
from pathlib import Path
from typing import Optional, List

from agents.base_agent import BaseAgent
from tools.knowledge_base import KnowledgeBase
from tools.web_search import WebSearch

_SYSTEM = """Du bist ein erfahrener Bildredakteur und Fotohistoriker mit Spezialisierung
auf die Geschichte der Werbebranche. Deine Aufgabe ist es, konkrete, recherchierbare
Bildquellen zur Agenturgeschichte zu identifizieren und zu dokumentieren.

Du kennst:
- Wikimedia Commons (commons.wikimedia.org) — freie historische Fotos
- Internet Archive (archive.org) — digitalisierte Werbezeitschriften, Annuals
- Duke University Ad*Access (library.duke.edu/digitalcollections/adaccess/)
- Getty Images Archive / Hulton Archive — lizenziertes Pressematerial
- Library of Congress Prints & Photographs (loc.gov/pictures/)
- Prelinger Archives (archive.org/details/prelinger) — Werbefilme
- D&AD Archive, One Show Archive — Kreativpreise & Einreichungen
- Taschen-Bibliographie: "The 100 Best Advertisements", "Art of Advertising"
- Fachjournale: Communication Arts, Print, Art Directors Annual (Jahrgänge als PDFs)

Antworte auf Deutsch. Nenne konkrete URLs, Suchbegriffe und Fundstellen."""

_VISUAL_PROMPT = """Erstelle einen konkreten Bildquellen-Bericht zu: **{topic}**

## Vorhandenes Bildmaterial
(Welche Art von historischem Bildmaterial existiert zu diesem Thema? Sei spezifisch.)

## Konkrete Archiv-Fundstellen
Für jede Quelle: Name, URL-Hinweis, empfohlene Suchbegriffe

### Freie Quellen (Wikimedia Commons, Internet Archive, Library of Congress)
- Quelle: [Name]
- Suchbegriff: [exakter Suchterm auf Englisch]
- URL-Hinweis: [Basis-URL oder Collection-Name]

### Lizenzierte Archive (Getty, Corbis)
- Quelle: [Name]
- Suchbegriff: [exakter Suchterm]

### Publikationen & Bücher
(Welche gedruckten Werke enthalten relevantes Bildmaterial zu diesem Thema?)

## Fotografen & Dokumentaristen
(Wer fotografierte diesen Bereich? Namen, Schaffenszeit, wo ihre Werke archiviert sind)

## Web-Suchergebnisse
{web_images}

## Suchstrategien
(Konkrete Tipps: welche englischen Suchbegriffe, welche Zeiträume, welche Spezialkollektionen)

## Metadaten
```json
{{
  "tags": ["visual", "bildquelle"],
  "era": "YYYY-YYYY",
  "category": "visuals",
  "confidence": "medium",
  "related_titles": []
}}
```"""


class Bildredakteur(BaseAgent):
    name = "bildredakteur"
    model_key = "bildredakteur"
    system_prompt = _SYSTEM

    def __init__(self, kb: KnowledgeBase):
        super().__init__()
        self.kb = kb
        self.search = WebSearch(
            cache_dir=kb.root.parent / "waves" / "_search_cache"
        )

    def research_visuals(self, topic: str, wave: int) -> Optional[Path]:
        print(f"  [Bildredakteur] Visuell recherchiere: {topic}")

        # Search multiple archives for real image sources
        queries = [
            f"{topic} site:commons.wikimedia.org",
            f"{topic} advertising agency historical photograph archive",
            f"{topic} site:archive.org advertising",
        ]
        web_images = ""
        for q in queries:
            results = self.search.search(q, max_results=3)
            if results:
                web_images += f"\n**Suche: `{q}`**\n" + "\n".join(
                    f"- [{r['title']}]({r['href']}): {r['body'][:200]}"
                    for r in results
                ) + "\n"

        prompt = _VISUAL_PROMPT.format(topic=topic, web_images=web_images or "(keine Ergebnisse)")
        raw = self.call(prompt, temperature=0.4)
        meta = _extract_meta(raw)
        meta["category"] = "visuals"
        content = _clean_content(raw)

        path = self.kb.write_entry(
            category="visuals",
            entry_id=f"visual_{topic}",
            title=f"Bildmaterial: {topic}",
            content=content,
            metadata=meta,
            wave=wave,
        )
        print(f"  [Bildredakteur] ✓ {path.relative_to(self.kb.root.parent)}")
        return path

    def annotate_existing(self, entry_title: str, entry_content: str,
                          wave: int) -> str:
        """Add visual annotations to an existing knowledge entry."""
        prompt = (
            f"Ergänze folgendes Wissens-Dokument um einen Abschnitt '## Bildmaterial':\n\n"
            f"**Thema:** {entry_title}\n\n{entry_content[:2000]}\n\n"
            f"Beschreibe in 5–8 Stichpunkten, welches historische Bildmaterial "
            f"zu diesem Thema existiert oder recherchiert werden sollte."
        )
        return self.call(prompt, temperature=0.4, max_tokens=1024)


def _extract_meta(text: str) -> dict:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    return {"tags": ["visual"], "era": "", "category": "visuals",
            "confidence": "medium", "related_titles": []}


def _clean_content(text: str) -> str:
    return re.sub(r"## Metadaten\s*```json.*?```", "", text, flags=re.DOTALL).strip()
