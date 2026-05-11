"""Historiker — deep research agent. Uses model knowledge + web search."""
import re
import json
from pathlib import Path
from typing import Optional, List

from agents.base_agent import BaseAgent
from tools.knowledge_base import KnowledgeBase
from tools.web_search import WebSearch

_SYSTEM = """Du bist ein führender Historiker der Werbe- und Kommunikationsbranche.
Dein Wissen umfasst die Geschichte internationaler Werbeagenturen (1880–2010),
insbesondere in den USA, UK und dem deutschsprachigen Raum.

Du kennst:
- Agentur-Gründungen, Fusionen, Charaktere und Kulturen
- Kreativ-Revolutionen, Strömungen, Manifeste und Gegenströmungen
- Tagesablauf, Rollen, Honorarmodelle, Pitches, Techniken
- Wichtige Kampagnen, ihre Entstehung und kulturelle Wirkung
- Werkzeuge und Ausstattung (Zeichentisch → Desktop Publishing)
- Skandale, Niederlagen, Triumphe

Antworte immer auf Deutsch. Sei präzise, nenne Jahreszahlen und Namen.
Kennzeichne Unsicherheiten mit (?) oder "möglicherweise"."""

_RESEARCH_PROMPT = """Erstelle einen umfassenden Wissensbeitrag über: **{topic}**

Strukturiere deinen Artikel exakt so:

## Überblick
(2–3 prägnante Sätze: Was ist das, warum ist es wichtig?)

## Historischer Kontext
(Zeitliche Einordnung, gesellschaftlicher/wirtschaftlicher Rahmen)

## Wichtige Details
(Fakten, Jahreszahlen, Namen, Ereignisse — konkret und belastbar)

## Bedeutung & Einfluss
(Welchen Einfluss hatte es auf die Branche, Kultur, spätere Entwicklungen?)

## Verbindungen
(Andere Agenturen, Personen, Kampagnen — nutze das Format [[Name]] für Links)

## Bildmaterial-Hinweise
(Was gibt es an historischem Bildmaterial? Fotos, Skizzen, Anzeigen, Interieur?)

## Metadaten
```json
{{
  "tags": ["tag1", "tag2", "tag3"],
  "era": "YYYY-YYYY",
  "category": "agencies",
  "confidence": "high",
  "related_titles": ["Titel1", "Titel2"]
}}
```

Mögliche Werte für "category": agencies, people, eras, work, life, technology, philosophy, scandals, visuals
{web_context}"""


class Historiker(BaseAgent):
    name = "historiker"
    model_key = "historiker"
    system_prompt = _SYSTEM

    def __init__(self, kb: KnowledgeBase, use_web: bool = True):
        super().__init__()
        self.kb = kb
        self.search = WebSearch(
            cache_dir=kb.root.parent / "waves" / "_search_cache"
        )
        self.use_web = use_web

    def research(self, topic: str, wave: int,
                 extra_context: str = "") -> Optional[Path]:
        print(f"  [Historiker] Recherchiere: {topic}")

        web_snippet = ""
        if self.use_web:
            results = self.search.search(
                f"Werbeagentur Geschichte {topic} advertising agency history",
                max_results=4,
            )
            if results:
                web_snippet = "\n\nWeb-Recherche (zusätzlicher Kontext):\n" + "\n".join(
                    f"- {r['title']}: {r['body'][:400]}"
                    for r in results[:3]
                )

        prompt = _RESEARCH_PROMPT.format(
            topic=topic,
            web_context=web_snippet + (f"\n\n{extra_context}" if extra_context else ""),
        )

        raw = self.call(prompt, temperature=0.35, max_tokens=8192)
        meta = _extract_meta(raw)
        content = _clean_content(raw)

        path = self.kb.write_entry(
            category=meta.get("category", "agencies"),
            entry_id=topic,
            title=topic,
            content=content,
            metadata=meta,
            wave=wave,
        )
        print(f"  [Historiker] ✓ {path.relative_to(self.kb.root.parent)}")
        return path

    def suggest_gaps(self, existing_topics: List[str]) -> List[str]:
        """Ask the model what important topics are still missing."""
        prompt = (
            f"Die folgenden Themen zur Agenturgeschichte sind bereits recherchiert:\n"
            + "\n".join(f"- {t}" for t in existing_topics)
            + "\n\nWelche 10 wichtigen Themen fehlen noch? "
            "Antworte nur mit einer nummerierten Liste (Deutsch, je 1 Zeile)."
        )
        raw = self.call(prompt, temperature=0.6, max_tokens=1024)
        gaps = []
        for line in raw.splitlines():
            line = re.sub(r"^\d+[\.\)]\s*", "", line.strip())
            if line:
                gaps.append(line)
        return gaps[:10]


def _extract_meta(text: str) -> dict:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return {
        "tags": [], "era": "", "category": "agencies",
        "confidence": "medium", "related_titles": [],
    }


def _clean_content(text: str) -> str:
    text = re.sub(r"## Metadaten\s*```json.*?```", "", text, flags=re.DOTALL)
    return text.strip()
