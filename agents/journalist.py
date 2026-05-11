"""Journalist — synthesizes clusters of knowledge into readable magazine articles."""
import re
from pathlib import Path
from typing import List, Optional, Dict

from agents.base_agent import BaseAgent
from tools.knowledge_base import KnowledgeBase

_SYSTEM = """Du bist ein erfahrener Fachjournalist und Autor, spezialisiert auf
Wirtschafts- und Kulturgeschichte der Werbebranche. Dein Stil: klar, lebendig,
mit konkreten Beispielen. Du schreibst für ein kultiviertes Fachpublikum das
sowohl Historiker als auch aktive Kreative umfasst.

Deine Texte sind:
- Gut strukturiert mit informativen Zwischenüberschriften
- Reich an konkreten Details, Zitaten und Anekdoten
- In einem flüssigen deutschen Magazin-Stil
- Frei von Klischees und Werbesprache"""

_ARTICLE_PROMPT = """Schreibe einen zusammenfassenden Überblicks-Artikel zum Thema: **{theme}**

Du hast Zugang zu folgenden Recherche-Dokumenten:

{snippets}

---

Schreibe einen kohärenten Magazin-Artikel (800–1200 Wörter) der:
1. Mit einem packenden Einstieg beginnt
2. Die wichtigsten Erkenntnisse aus den Dokumenten verwebt
3. Querverbindungen und Muster herausarbeitet
4. Mit einem Fazit / Ausblick endet

Verwende [[Wikilinks]] für wichtige Personen, Agenturen und Konzepte.
Artikel-Titel: **{theme} — Ein Überblick**"""


class Journalist(BaseAgent):
    name = "journalist"
    model_key = "journalist"
    system_prompt = _SYSTEM

    def __init__(self, kb: KnowledgeBase):
        super().__init__()
        self.kb = kb

    def write_overview(self, theme: str, entries: List[Dict],
                       wave: int) -> Optional[Path]:
        """Write a synthesized overview article from multiple knowledge entries."""
        print(f"  [Journalist] Schreibe Überblick: {theme}")

        snippets = "\n\n---\n\n".join(
            f"### {e['meta'].get('title', 'Unbekannt')}\n\n"
            f"{e['content'][:1500]}"
            for e in entries[:6]
        )

        prompt = _ARTICLE_PROMPT.format(theme=theme, snippets=snippets)
        article = self.call(prompt, temperature=0.6, max_tokens=6144)

        tags = []
        for e in entries:
            tags.extend(e["meta"].get("tags", []))
        tags = list(set(tags))[:10]

        path = self.kb.write_entry(
            category="eras",
            entry_id=f"overview_{theme}",
            title=f"Überblick: {theme}",
            content=article,
            metadata={
                "tags": ["überblick", "synthese"] + tags,
                "confidence": "high",
                "sources": [str(e["path"]) for e in entries],
            },
            wave=wave,
        )
        print(f"  [Journalist] ✓ {path.relative_to(self.kb.root.parent)}")
        return path

    def write_profile(self, subject: str, entries: List[Dict],
                      wave: int) -> Optional[Path]:
        """Write a detailed profile of a person or agency."""
        print(f"  [Journalist] Schreibe Profil: {subject}")

        snippets = "\n\n---\n\n".join(
            f"**{e['meta'].get('title', '')}**\n{e['content'][:1200]}"
            for e in entries[:4]
        )
        prompt = (
            f"Schreibe ein ausführliches Porträt über: **{subject}**\n\n"
            f"Quellmaterial:\n{snippets}\n\n"
            f"Das Porträt soll 600–900 Wörter haben, im lebendigen Magazin-Stil, "
            f"mit konkreten Anekdoten und präzisen Details. "
            f"Nutze [[Wikilinks]] für wichtige Bezüge."
        )
        profile = self.call(prompt, temperature=0.65, max_tokens=4096)

        path = self.kb.write_entry(
            category="people",
            entry_id=f"profile_{subject}",
            title=f"Porträt: {subject}",
            content=profile,
            metadata={"tags": ["porträt", "profil"], "confidence": "high"},
            wave=wave,
        )
        print(f"  [Journalist] ✓ {path.relative_to(self.kb.root.parent)}")
        return path

    def identify_clusters(self, entries: List[Dict]) -> List[Dict]:
        """Ask model to identify thematic clusters in the knowledge base."""
        titles = [e["meta"].get("title", "") for e in entries]
        prompt = (
            "Identifiziere 5–8 thematische Cluster aus dieser Liste von Wissenseinträgen:\n"
            + "\n".join(f"- {t}" for t in titles)
            + "\n\nGib für jeden Cluster an: Name des Clusters, und welche Einträge dazu gehören.\n"
            "Format: CLUSTER: [Name]\nEINTRÄGE: [Eintrag1, Eintrag2, ...]"
        )
        raw = self.call(prompt, temperature=0.4, max_tokens=2048)
        clusters = []
        current = None
        for line in raw.splitlines():
            if line.startswith("CLUSTER:"):
                current = {"name": line.replace("CLUSTER:", "").strip(), "items": []}
                clusters.append(current)
            elif line.startswith("EINTRÄGE:") and current:
                items_str = line.replace("EINTRÄGE:", "").strip()
                current["items"] = [i.strip() for i in items_str.split(",")]
        return clusters
