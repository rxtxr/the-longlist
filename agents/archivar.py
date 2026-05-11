"""Archivar — librarian agent. Maintains GRAPH.md, semantic tags, and cross-links."""
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from agents.base_agent import BaseAgent
from tools.knowledge_base import KnowledgeBase
from config import CATEGORIES, CATEGORY_LABELS, KNOWLEDGE_DIR

_SYSTEM = """Du bist ein präziser Archivar und Wissensorganisator.
Deine Aufgabe ist es, eine strukturierte Wissensdatenbank zur Agenturgeschichte zu pflegen.

Du:
- Erkennst Zusammenhänge zwischen Einträgen
- Vergibst konsistente, sinnvolle Tags
- Identifizierst fehlende Verknüpfungen
- Erkennst Duplikate und Überlappungen
- Schlägst neue Themen vor die noch fehlen

Antworte strukturiert und präzise. Keine Interpretationen, nur Fakten und Verknüpfungen."""


class Archivar(BaseAgent):
    name = "archivar"
    model_key = "archivar"
    system_prompt = _SYSTEM

    def __init__(self, kb: KnowledgeBase):
        super().__init__()
        self.kb = kb

    def update_graph(self) -> Path:
        """Rebuild GRAPH.md from current knowledge base state."""
        print("  [Archivar] Aktualisiere Wissens-Graph...")

        stats = self.kb.get_stats()
        all_tags = self.kb.all_tags()
        entries = self.kb.list_all()

        lines = [
            "# Wissens-Graph — Agenturgeschichte\n",
            f"_Zuletzt aktualisiert: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n",
            f"_Einträge gesamt: {stats['total']}_\n",
            "",
            "## Statistiken\n",
        ]

        for cat in CATEGORIES:
            count = stats.get(cat, 0)
            label = CATEGORY_LABELS.get(cat, cat)
            lines.append(f"- **{label}**: {count} Einträge")

        lines += ["", "## Einträge nach Kategorie\n"]

        for cat in CATEGORIES:
            cat_entries = self.kb.list_category(cat)
            if not cat_entries:
                continue
            label = CATEGORY_LABELS.get(cat, cat)
            lines.append(f"### {label}\n")
            for e in cat_entries:
                meta = e["meta"]
                title = meta.get("title", "?")
                era = meta.get("era", "")
                tags = meta.get("tags", [])
                tags_str = ", ".join(f"`{t}`" for t in tags[:4])
                era_str = f" _{era}_" if era else ""
                fname = e["path"].name
                lines.append(f"- [{title}](knowledge/{cat}/{fname}){era_str} {tags_str}")
            lines.append("")

        lines += ["## Tag-Index\n"]
        top_tags = sorted(all_tags.items(), key=lambda x: -x[1])[:40]
        for tag, count in top_tags:
            lines.append(f"- `{tag}` ({count}×)")

        lines += ["", "## Offene Lücken\n",
                  "_Wird nach jeder Welle durch den Historiker aktualisiert._\n"]

        graph_path = self.kb.root / "GRAPH.md"
        graph_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  [Archivar] ✓ GRAPH.md ({stats['total']} Einträge)")
        return graph_path

    def enrich_links(self, wave: int) -> int:
        """Add [[wikilinks]] to entries that reference known titles."""
        known_titles = {
            e["meta"].get("title", "").lower(): e
            for e in self.kb.list_all()
        }
        enriched = 0

        for entry in self.kb.list_all():
            content = entry["content"]
            changed = False

            for title, target in known_titles.items():
                if target["path"] == entry["path"]:
                    continue
                if title in content.lower() and f"[[{target['meta']['title']}]]" not in content:
                    pattern = re.compile(re.escape(target["meta"]["title"]), re.IGNORECASE)
                    new_content = pattern.sub(f"[[{target['meta']['title']}]]", content, count=1)
                    if new_content != content:
                        content = new_content
                        changed = True

            if changed:
                entry["path"].write_text(
                    re.sub(r"^---.*?---\n", "", entry["path"].read_text(), flags=re.DOTALL, count=1),
                    encoding="utf-8"
                )
                import frontmatter as fm
                post = fm.load(str(entry["path"]))
                post.content = content
                entry["path"].write_text(fm.dumps(post), encoding="utf-8")
                enriched += 1

        print(f"  [Archivar] Links angereichert: {enriched} Einträge")
        return enriched

    def find_duplicates(self) -> List[Dict]:
        """Identify potentially duplicate entries."""
        entries = self.kb.list_all()
        titles = [(e["meta"].get("title", ""), e) for e in entries]
        duplicates = []

        for i, (t1, e1) in enumerate(titles):
            for t2, e2 in titles[i+1:]:
                similarity = _jaccard_similarity(
                    set(t1.lower().split()),
                    set(t2.lower().split())
                )
                if similarity > 0.7:
                    duplicates.append({"entry1": e1, "entry2": e2, "similarity": similarity})

        return duplicates

    def suggest_links(self, entry: Dict) -> List[str]:
        """Ask model to suggest semantic links for an entry."""
        all_titles = [e["meta"].get("title", "") for e in self.kb.list_all()]
        prompt = (
            f"Welche der folgenden Themen sind semantisch verwandt mit: "
            f"**{entry['meta'].get('title', '')}**?\n\n"
            f"Verfügbare Themen:\n"
            + "\n".join(f"- {t}" for t in all_titles[:60])
            + "\n\nNenne die 5 relevantesten, je mit kurzer Begründung (1 Satz)."
        )
        raw = self.call(prompt, temperature=0.3, max_tokens=1024)
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def generate_gap_report(self, existing_topics: List[str], wave: int) -> Path:
        """Ask model to identify missing topics and save as gap report."""
        prompt = (
            f"Die folgenden {len(existing_topics)} Themen zur Agenturgeschichte sind bereits dokumentiert:\n"
            + "\n".join(f"- {t}" for t in existing_topics[:80])
            + "\n\nWelche wichtigen Themen fehlen noch? Schlage 15 fehlende Themen vor.\n"
            "Kategorisiere jeden Vorschlag: agencies, people, eras, work, life, "
            "technology, philosophy, scandals oder visuals.\n"
            "Format pro Zeile: KATEGORIE: Thema — kurze Begründung warum wichtig"
        )
        raw = self.call(prompt, temperature=0.5, max_tokens=2048)

        wave_dir = self.kb.root.parent / "waves" / f"wave-{wave:03d}"
        wave_dir.mkdir(parents=True, exist_ok=True)
        gap_path = wave_dir / "gap_report.md"
        gap_path.write_text(
            f"# Gap Report — Welle {wave}\n\n"
            f"_Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n"
            f"## Fehlende Themen\n\n{raw}\n",
            encoding="utf-8",
        )
        print(f"  [Archivar] ✓ Gap Report: {gap_path.relative_to(self.kb.root.parent)}")
        return gap_path


def _jaccard_similarity(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
