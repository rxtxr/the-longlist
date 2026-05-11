"""Redakteur — narrative enrichment agent.

Takes a verified, fact-checked article and rewrites it with story, context,
and significance. All [ungesichert] markers are preserved. New narrative claims
that can't be backed by sources are also marked [ungesichert].
The goal: readable, engaging articles that still respect factual rigor.
"""
import re
from typing import Dict, List, Optional

from agents.base_agent import BaseAgent
from tools.knowledge_base import KnowledgeBase
from tools.web_search import WebSearch

_SYSTEM = """Du bist ein erfahrener Kulturjournalist und Historiker der Werbebranche.
Deine Texte sind lebendig, anekdotenreich und fesselnd — aber du hältst dich an belegte Fakten.

Du schreibst für ein Publikum, das nicht nur Fakten will, sondern verstehen möchte:
- Warum war das wichtig?
- Was ist die Geschichte dahinter?
- Wer waren die Menschen, was trieb sie an?
- Was hat sich dadurch verändert?

GRUNDREGELN:
- Alle bestehenden [ungesichert]-Markierungen bleiben unverändert erhalten
- Neue erzählerische Aussagen ohne klare Quelle: ebenfalls mit [ungesichert] kennzeichnen
- Keine neuen konkreten Jahreszahlen, Namen oder Zitate erfinden
- Wo die Quellenlage dünn ist: das offen benennen, trotzdem den Kontext erklären
- Antworte auf Deutsch"""

_RELEVANCE_PROMPT = """Überarbeite diesen Artikel — bring die Geschichte heraus.

## Artikel: {title}
## Kategorie: {category}

{content}

## Web-Quellen und Kontext:
{web_context}

## Deine Aufgabe:

Schreibe den Artikel lebendig und relevant. Fokus auf:

1. **Die Geschichte**: Was macht diesen Eintrag interessant? Was steckt dahinter?
2. **Bedeutung und Wirkung**: Warum sollte jemand das kennen? Was hat es verändert?
3. **Kontext und Zeitgeist**: In welcher Welt entstand das? Was war damals normal, was war neu?
4. **Menschen und Charaktere**: Wer steckt dahinter, was trieb sie an?
5. **Anekdoten und Details**: Konkrete Szenen oder Geschichten, die den Eintrag lebendig machen

BEHALTE die Struktur:
## Überblick
## Historischer Kontext
## Wichtige Details
## Bedeutung & Einfluss
## Verbindungen
## Bildmaterial-Hinweise

BEACHTE:
- Alle bestehenden [ungesichert]-Markierungen exakt beibehalten
- Neue unsichere/erzählerische Aussagen mit [ungesichert] markieren
- Wenn die Quellenlage eine Geschichte nicht hergibt: schreibe "Die Quellenlage hierzu ist dünn — [ungesichert]" und erkläre trotzdem den historischen Kontext
- Nutze Wikilinks [[Name]] für Personen und Agenturen

Am Ende:
## Quellen
```json
{{"genutzt": ["Quelle 1", "Quelle 2"], "offen": ["Was noch recherchiert werden sollte"]}}
```"""

_MINIMAL_RELEVANCE_PROMPT = """Überarbeite diesen Artikel — bring die Geschichte heraus.
Quellenlage ist begrenzt, aber erkläre trotzdem Bedeutung und Kontext.

## Artikel: {title}

{content}

## Web-Quellen:
{web_context}

Schreibe lebendig und kontextualisiert. Alle [ungesichert]-Markierungen beibehalten.
Neue unsichere Aussagen mit [ungesichert] kennzeichnen. Struktur beibehalten.

Am Ende:
## Quellen
```json
{{"genutzt": [], "offen": []}}
```"""


class Redakteur(BaseAgent):
    name = "redakteur"
    model_key = "default"
    system_prompt = _SYSTEM

    def __init__(self, kb: KnowledgeBase):
        super().__init__()
        self.kb = kb
        self.search = WebSearch(
            cache_dir=kb.root.parent / "waves" / "_search_cache"
        )

    def enrich_entry(self, entry: Dict, wave: int) -> bool:
        """Rewrite one KB entry for narrative quality. Returns True if changed."""
        meta = entry["meta"]
        content = entry["content"]
        title = meta.get("title", entry["path"].stem)
        category = entry["path"].parent.name

        if category == "visuals":
            return False

        print(f"  [Redakteur] {title[:65]}")

        sources = self._gather_sources(title, category)
        web_context = self._format_sources(sources) if sources else "(keine Web-Quellen)"
        source_count = len(sources)

        if source_count >= 2:
            prompt = _RELEVANCE_PROMPT.format(
                title=title,
                category=category,
                content=content[:5500],
                web_context=web_context,
            )
        else:
            prompt = _MINIMAL_RELEVANCE_PROMPT.format(
                title=title,
                content=content[:5500],
                web_context=web_context,
            )

        raw = self.call(prompt, temperature=0.55, max_tokens=6000)

        if not raw or len(raw.strip()) < 300:
            print(f"    → leere Ausgabe, übersprungen")
            return False

        new_content = _extract_article(raw)
        if not new_content or len(new_content) < 400:
            print(f"    → unbrauchbare Ausgabe, übersprungen")
            return False

        uncertain_count = new_content.count("[ungesichert]")
        thin_sources = "Quellenlage" in new_content and "dünn" in new_content
        status_parts = []
        if uncertain_count:
            status_parts.append(f"{uncertain_count}× [ungesichert]")
        if thin_sources:
            status_parts.append("dünne Quellenlage vermerkt")
        print(f"    ✓ {', '.join(status_parts) if status_parts else 'angereichert'}")

        sources_meta = _extract_sources_meta(raw)
        updated_meta = dict(meta)
        updated_meta["relevance_wave"] = wave
        if sources_meta.get("genutzt"):
            existing = updated_meta.get("sources", [])
            merged = list(existing)
            for s in sources_meta["genutzt"]:
                if s not in merged:
                    merged.append(s)
            updated_meta["sources"] = merged
        if uncertain_count > 5:
            updated_meta["confidence"] = "low"
        elif uncertain_count > 2 and updated_meta.get("confidence") == "high":
            updated_meta["confidence"] = "medium"

        self.kb.write_entry(
            category=category,
            entry_id=entry["path"].stem,
            title=title,
            content=new_content,
            metadata=updated_meta,
            wave=wave,
        )
        return True

    def _gather_sources(self, title: str, category: str) -> List[Dict]:
        short = re.split(r'\s[—–-]\s', title)[0].strip()
        short = re.sub(r'\s*\([^)]*\d{4}[^)]*\)', '', short).strip()

        queries = [
            f'"{short}" advertising history story significance',
            f'"{short}" Werbebranche Geschichte Bedeutung',
            f'site:wikipedia.org "{short}"',
        ]
        if category == "people":
            queries += [
                f'"{short}" interview biography personality advertising',
                f'"{short}" Werber Karriere Anekdote',
            ]
        elif category == "agencies":
            queries += [
                f'"{short}" agency culture founding story advertising',
                f'"{short}" Agentur Gründung Kultur Kampagne',
            ]
        elif category == "work":
            queries += [
                f'"{short}" campaign behind the scenes making of',
            ]
        elif category == "eras":
            queries += [
                f'"{short}" advertising era zeitgeist culture',
            ]
        elif category == "scandals":
            queries += [
                f'"{short}" advertising scandal controversy impact',
            ]

        seen_urls: set = set()
        results = []
        for q in queries:
            for r in self.search.search(q, max_results=3):
                url = r.get("href", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    results.append(r)
            if len(results) >= 8:
                break
        return results[:8]

    def _format_sources(self, sources: List[Dict]) -> str:
        lines = []
        for i, r in enumerate(sources, 1):
            title = r.get("title", "")
            body = r.get("body", "")[:400]
            href = r.get("href", "")
            lines.append(f"[{i}] {title}\n    {href}\n    {body}")
        return "\n\n".join(lines)


def _extract_article(text: str) -> str:
    article = re.sub(r"\n## Quellen.*", "", text, flags=re.DOTALL)
    match = re.search(r"(## Überblick.*)", article, re.DOTALL)
    if match:
        return match.group(1).strip()
    if len(article.strip()) > 300:
        return article.strip()
    return ""


def _extract_sources_meta(text: str) -> Dict:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            import json
            return json.loads(match.group(1))
        except Exception:
            pass
    return {}
