"""StrictVerifier — source-mandatory fact checker.
Every factual claim must be backed by web evidence or marked [ungesichert].
Claims that exist nowhere outside this wiki are hallucinations and get removed.
"""
import re
import json
from pathlib import Path
from typing import Optional, Dict, List

from agents.base_agent import BaseAgent
from tools.knowledge_base import KnowledgeBase
from tools.web_search import WebSearch

_SYSTEM = """Du bist ein strenger Faktenprüfer für historische Artikel über die Werbebranche.

GRUNDREGEL: Jede faktische Aussage in einem Artikel muss durch externe Quellen belegbar sein.
Informationen, die nur im Artikel selbst existieren und nirgends anders auftauchen, sind Halluzinationen.

DEINE AUFGABE:
1. Prüfe jeden Satz gegen die Web-Quellen
2. Markiere Aussagen ohne Quellenbeleg mit [ungesichert]
3. Entferne Aussagen, die den Quellen widersprechen oder nirgends auffindbar sind
4. Füge am Ende eine Quellenliste ein

MARKIERUNGEN:
- (?) hinter einer konkreten Angabe = unsichere Zahl/Datum, nicht eindeutig belegt
- [ungesichert] am Satzende = plausibel, aber keine direkte Quelle gefunden
- Komplett erfundene Fakten (nur im Wiki, nirgends sonst) → einfach löschen

SCHREIBE NIE:
- Konkrete Jahreszahlen die du in keiner Quelle findest
- Zitate die du nicht verifizieren kannst
- Namen in konkreten Rollen die du nicht belegen kannst
- Detaillierte Anekdoten die nirgends dokumentiert sind

SCHREIBE STATTDESSEN:
- "in den frühen 1960er Jahren" statt "1962" wenn das Jahr nicht belegt ist
- "war an der Kampagne beteiligt" statt "leitete die Kampagne" wenn die Rolle unklar ist
- Weglassen statt erfinden

Antworte auf Deutsch. Sei konservativ lieber als erfindungsreich."""

_STRICT_PROMPT = """Überarbeite diesen Artikel mit Quellenpflicht.

## Artikel: {title}
## Kategorie: {category}

{content}

## Verfügbare Web-Quellen:
{web_context}

## Aufgabe:
Schreibe den Artikel vollständig neu. Für jeden Abschnitt:

1. Behalte nur Aussagen, die durch die Web-Quellen oder allgemeines historisches Wissen belegt sind
2. Markiere ungesicherte aber plausible Aussagen mit [ungesichert]
3. Lösche alles was nur in diesem Artikel existiert und nirgends sonst auffindbar ist
4. Füge konkrete Quellenverweise ein wo möglich (z.B. "laut Campaign Magazine", "nach Ad Age")

Struktur beibehalten:
## Überblick
## Historischer Kontext
## Wichtige Details
## Bedeutung & Einfluss
## Verbindungen
## Bildmaterial-Hinweise

Am Ende:
## Quellen
```json
{{"belegt": ["Quelle 1", "Quelle 2"], "ungesichert": ["Liste was nicht belegt werden konnte"]}}
```

WICHTIG: Wenn du zu wenig Web-Quellen hast um den Artikel zu beurteilen, schreibe nur:
UNZUREICHENDE_QUELLEN"""

_MINIMAL_PROMPT = """Überarbeite diesen Artikel konservativ.

## Artikel: {title}

{content}

## Web-Quellen (begrenzt):
{web_context}

Entferne nur klar widersprüchliche Angaben. Markiere alles was du nicht durch die Quellen
bestätigen kannst mit [ungesichert]. Füge (?) hinter unsicheren Jahreszahlen ein.

Behalte die Struktur. Am Ende:
## Quellen
```json
{{"belegt": [], "ungesichert": []}}
```"""


class StrictVerifier(BaseAgent):
    name = "strict_verifier"
    model_key = "verifier"
    system_prompt = _SYSTEM

    def __init__(self, kb: KnowledgeBase):
        super().__init__()
        self.kb = kb
        self.search = WebSearch(
            cache_dir=kb.root.parent / "waves" / "_search_cache"
        )

    def verify_entry(self, entry: Dict, wave: int) -> bool:
        """Strictly verify one KB entry. Returns True if article was rewritten."""
        meta = entry["meta"]
        content = entry["content"]
        title = meta.get("title", entry["path"].stem)
        category = entry["path"].parent.name

        if category == "visuals":
            return False

        print(f"  [StrictVerifier] {title[:65]}")

        # Multiple targeted searches for better coverage
        sources = self._gather_sources(title, category)

        if not sources:
            print(f"    → keine Quellen, übersprungen")
            return False

        web_context = self._format_sources(sources)
        source_count = len(sources)

        # Choose prompt based on source coverage
        if source_count >= 3:
            prompt = _STRICT_PROMPT.format(
                title=title,
                category=category,
                content=content[:5500],
                web_context=web_context,
            )
        else:
            prompt = _MINIMAL_PROMPT.format(
                title=title,
                content=content[:5500],
                web_context=web_context,
            )

        raw = self.call(prompt, temperature=0.15, max_tokens=6000)

        if not raw or "UNZUREICHENDE_QUELLEN" in raw:
            print(f"    → unzureichende Quellen ({source_count}), übersprungen")
            return False

        new_content = _extract_article(raw)
        if not new_content or len(new_content) < 400:
            print(f"    → leere Ausgabe, übersprungen")
            return False

        # Count [ungesichert] markers added
        uncertain_count = new_content.count("[ungesichert]")
        removed = _estimate_removed(content, new_content)

        status = []
        if uncertain_count:
            status.append(f"{uncertain_count}× [ungesichert]")
        if removed:
            status.append(f"~{removed} Sätze entfernt")
        if not status:
            status.append("bereinigt")
        print(f"    ✓ {', '.join(status)}")

        # Extract sources for metadata
        sources_meta = _extract_sources_meta(raw)

        updated_meta = dict(meta)
        updated_meta["strict_verified_wave"] = wave
        if sources_meta.get("belegt"):
            updated_meta["sources"] = sources_meta["belegt"]
        if sources_meta.get("ungesichert"):
            updated_meta["ungesichert"] = sources_meta["ungesichert"]
        # Downgrade confidence if many unverified claims
        if uncertain_count > 5:
            updated_meta["confidence"] = "low"
        elif uncertain_count > 2:
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
        """Multi-query search: trade press, Wikipedia, books, archives."""
        short = re.split(r'\s[—–-]\s', title)[0].strip()
        # Strip parenthetical year ranges like "(1929, 1973, 2008)" or "(1960er–1990er)"
        short = re.sub(r'\s*\([^)]*\d{4}[^)]*\)', '', short).strip()

        # Prioritize authoritative sources: Ad Age, Campaign, Wikipedia, books
        queries = [
            f'site:wikipedia.org "{short}" advertising',
            f'"{short}" site:adage.com OR site:campaignlive.co.uk OR site:adweek.com',
            f'"{short}" advertising history',
            f'"{short}" Werbeagentur Geschichte',
        ]
        if category == "people":
            queries += [
                f'"{short}" biography born died advertising',
                f'"{short}" book author advertising',
            ]
        elif category == "agencies":
            queries += [
                f'"{short}" founded merged acquired advertising agency',
            ]
        elif category == "work":
            queries += [
                f'"{short}" advertising campaign year client',
            ]
        elif category == "scandals":
            queries += [
                f'"{short}" scandal controversy advertising',
            ]
        elif category == "eras":
            queries += [
                f'"{short}" advertising decade history timeline',
            ]

        seen_urls = set()
        all_results = []
        for q in queries:
            for r in self.search.search(q, max_results=4):
                url = r.get("href", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
            if len(all_results) >= 10:
                break
        return all_results[:10]

    def _format_sources(self, sources: List[Dict]) -> str:
        lines = []
        for i, r in enumerate(sources, 1):
            title = r.get("title", "")
            body = r.get("body", "")[:400]
            href = r.get("href", "")
            lines.append(f"[{i}] {title}\n    {href}\n    {body}")
        return "\n\n".join(lines)


def _extract_article(text: str) -> str:
    # Strip sources block at end
    article = re.sub(r"\n## Quellen.*", "", text, flags=re.DOTALL)
    # Must start from ## Überblick
    match = re.search(r"(## Überblick.*)", article, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: return everything if structure is slightly different
    if len(article.strip()) > 300:
        return article.strip()
    return ""


def _extract_sources_meta(text: str) -> Dict:
    match = re.search(
        r"## Quellen\s*```json\s*(\{.*?\})\s*```", text, re.DOTALL
    )
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return {"belegt": [], "ungesichert": []}


def _estimate_removed(old: str, new: str) -> int:
    """Rough estimate of how many sentences were removed."""
    old_sents = len(re.findall(r'[.!?]\s', old))
    new_sents = len(re.findall(r'[.!?]\s', new))
    return max(0, old_sents - new_sents)
