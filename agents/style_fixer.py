"""StyleFixer — removes the 'mehr als nur / more than just' tic from Überblick sections.

This is a surgical rewrite: only the ## Überblick section is sent to the LLM.
All other content (metadata, other sections) is untouched.
"""
import re
from typing import Optional

import frontmatter

from agents.base_agent import BaseAgent
from tools.knowledge_base import KnowledgeBase

_PATTERNS = [
    r'mehr als nur',
    r'weit mehr als',
    r'viel mehr als',
    r'more than just',
    r'nicht nur .{0,60}sondern',
]

_SYSTEM = """Du bist Lektor eines Fachlexikons. Deine einzige Aufgabe: Schwache Einstiege stärken.

Das Muster "X ist mehr als nur Y — X ist Z" ist ein Klischee. Es signalisiert Unsicherheit.
Stärke stattdessen direkt: "X ist Z."

REGELN:
- Entferne alle Varianten: "mehr als nur", "weit mehr als", "nicht nur ... sondern", "more than just"
- Schreibe direkt und selbstbewusst, ohne Relativierungen
- Behalte alle inhaltlichen Informationen — nur die Formulierung ändert sich
- Keine neuen Fakten erfinden
- Antworte NUR mit dem überarbeiteten Abschnitt, kein Kommentar"""

_PROMPT = """Überarbeite diesen Überblick-Abschnitt. Entferne alle "mehr als nur / weit mehr als / not just"-Muster.

Titel: {title}

{section}

Gib nur den überarbeiteten Text zurück (ohne "## Überblick"-Überschrift)."""


def _has_pattern(text: str) -> bool:
    for p in _PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def _extract_ueberblick(content: str) -> Optional[str]:
    m = re.search(r'## Überblick\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    return m.group(1).strip() if m else None


def _replace_ueberblick(content: str, new_text: str) -> str:
    return re.sub(
        r'(## Überblick\n).*?(?=\n## |\Z)',
        r'\g<1>' + new_text.strip() + '\n',
        content, count=1, flags=re.DOTALL,
    )


class StyleFixer(BaseAgent):
    name = "style_fixer"
    model_key = "archivar"
    system_prompt = _SYSTEM

    def __init__(self, kb: KnowledgeBase):
        super().__init__()
        self.kb = kb

    def fix_entry(self, path, title: str, content: str) -> Optional[str]:
        section = _extract_ueberblick(content)
        if not section or not _has_pattern(section):
            return None

        prompt = _PROMPT.format(title=title, section=section)
        new_section = self.call(prompt, temperature=0.15, max_tokens=600)

        if not new_section or len(new_section.strip()) < 50:
            return None
        if _has_pattern(new_section):
            # Model still used the pattern — try once more with stricter instruction
            stricter = prompt + "\n\nWICHTIG: Der neue Text darf KEINESFALLS 'mehr als', 'weit mehr', 'not just' enthalten."
            new_section = self.call(stricter, temperature=0.1, max_tokens=600)
            if not new_section or _has_pattern(new_section):
                return None

        return _replace_ueberblick(content, new_section)

    def run_wave(self, dry_run: bool = False):
        entries = list(self.kb.list_all())
        flagged = []
        for e in entries:
            section = _extract_ueberblick(e["content"])
            if section and _has_pattern(section):
                flagged.append(e)

        print(f"\n[StyleFixer] {len(flagged)} Artikel mit 'mehr als nur'-Muster")
        fixed = skipped = errors = 0

        for i, entry in enumerate(flagged, 1):
            path = entry["path"]
            meta = entry["meta"]
            title = meta.get("title", path.stem)
            cat = path.parent.name
            print(f"  [{i}/{len(flagged)}] {title[:60]}")

            if dry_run:
                skipped += 1
                continue

            new_content = self.fix_entry(path, title, entry["content"])
            if not new_content:
                skipped += 1
                continue

            try:
                e = frontmatter.load(str(path))
                e.content = new_content
                path.write_text(frontmatter.dumps(e), encoding="utf-8")
                fixed += 1
                print(f"    ✓ überarbeitet")
            except Exception as ex:
                print(f"    ✗ Fehler: {ex}")
                errors += 1

        print(f"\n[StyleFixer] Fertig: {fixed} überarbeitet, {skipped} übersprungen, {errors} Fehler")
        return {"fixed": fixed, "skipped": skipped, "errors": errors}
