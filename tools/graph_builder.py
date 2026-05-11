"""Graph builder — reads knowledge base and produces graph.json (nodes + edges) for D3.js."""
import warnings; warnings.filterwarnings("ignore")
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

import frontmatter as fm

from config import CATEGORIES, KNOWLEDGE_DIR
from tools.ontology import ENTITY_TYPES, CATEGORY_ENTITY_TYPE, RELATION_TYPES


class GraphBuilder:
    def __init__(self, kb=None):
        self.kb = kb
        self.out_path = Path(__file__).parent.parent / "wiki" / "graph.json"

    def build(self) -> Dict:
        entries = self._load_entries()
        id_map: Dict[str, Dict] = {}
        nodes: List[Dict] = []
        edges: List[Dict] = []
        seen_edges: Set[str] = set()

        # Pass 1: build nodes (deduplicate: if same id appears in multiple categories, qualify it)
        # First pass: count how many entries share each meta id
        id_count: Dict[str, int] = {}
        for entry in entries:
            meta = entry["meta"]
            raw_id = meta.get("id", entry["path"].stem)
            id_count[raw_id] = id_count.get(raw_id, 0) + 1

        for entry in entries:
            meta = entry["meta"]
            raw_id = meta.get("id", entry["path"].stem)
            cat = entry["path"].parent.name
            # If this ID is shared across categories, qualify with category prefix
            if id_count[raw_id] > 1:
                node_id = f"{cat}__{raw_id}"
            else:
                node_id = raw_id
            entity_type = meta.get("entity_type", CATEGORY_ENTITY_TYPE.get(cat, "concept"))
            color = ENTITY_TYPES.get(entity_type, {}).get("color", "#888")
            nodes.append({
                "id": node_id,
                "label": meta.get("title", node_id),
                "type": entity_type,
                "category": cat,
                "color": color,
                "era_from": meta.get("era_from"),
                "era_to": meta.get("era_to"),
                "geo_region": meta.get("geo_region"),
                "path": f"pages/{cat}/{entry['path'].stem}.html",
            })
            id_map[node_id] = entry

        valid_ids = set(id_map.keys())

        def add_edge(src, tgt, rel_type, label=""):
            if src not in valid_ids or tgt not in valid_ids or src == tgt:
                return
            key = f"{src}|{tgt}|{rel_type}"
            rev = f"{tgt}|{src}|{rel_type}"
            if key in seen_edges or rev in seen_edges:
                return
            seen_edges.add(key)
            edges.append({
                "source": src,
                "target": tgt,
                "type": rel_type,
                "label": label or RELATION_TYPES.get(rel_type, {}).get("label", rel_type),
            })

        # Pass 2: frontmatter relations + legacy related list
        for entry in entries:
            meta = entry["meta"]
            node_id = meta.get("id", entry["path"].stem)
            for rel in meta.get("relations", []):
                add_edge(node_id, rel.get("target_id", ""), rel.get("type", "related"), rel.get("label", ""))
            for related_title in meta.get("related", []):
                add_edge(node_id, self._slugify(str(related_title)), "related")

        # Pass 3: content-mention edges (short name found in another entry's text)
        # Extract short name (before em-dash/en-dash/spaced-hyphen) for better matching
        title_to_id: Dict[str, str] = {}
        for entry in entries:
            meta = entry["meta"]
            node_id = meta.get("id", entry["path"].stem)
            title = meta.get("title", "")
            if not title:
                continue
            # Use short name (before dash separator) for content matching
            short = re.split(r'\s[—–-]\s', title)[0].strip()
            search_term = short if short else title
            if len(search_term) > 4:
                title_to_id[search_term.lower()] = node_id
            # Also index the full title if it's reasonably unique
            if title != short and len(title) > 8:
                title_to_id[title.lower()] = node_id

        for entry in entries:
            meta = entry["meta"]
            node_id = meta.get("id", entry["path"].stem)
            content_lower = entry["content"].lower()
            cat_src = entry["path"].parent.name
            for search_term, tgt_id in title_to_id.items():
                if tgt_id == node_id:
                    continue
                if search_term in content_lower:
                    cat_tgt = id_map[tgt_id]["path"].parent.name if tgt_id in id_map else ""
                    rel_type = _infer_rel(cat_src, cat_tgt)
                    add_edge(node_id, tgt_id, rel_type)

        # Pass 4: shared-tag edges (1+ common tag → "related", lowered threshold)
        tag_to_nodes: Dict[str, List[str]] = defaultdict(list)
        for entry in entries:
            meta = entry["meta"]
            node_id = meta.get("id", entry["path"].stem)
            for tag in meta.get("tags", []):
                if tag and len(tag) > 3:
                    tag_to_nodes[tag.lower()].append(node_id)

        shared: Dict[tuple, int] = defaultdict(int)
        for nodes_with_tag in tag_to_nodes.values():
            if len(nodes_with_tag) < 2:
                continue
            for i in range(len(nodes_with_tag)):
                for j in range(i + 1, len(nodes_with_tag)):
                    pair = tuple(sorted([nodes_with_tag[i], nodes_with_tag[j]]))
                    shared[pair] += 1
        for (a, b), count in shared.items():
            if count >= 1:
                add_edge(a, b, "related")

        graph = {"nodes": nodes, "edges": edges}
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        self.out_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [GraphBuilder] ✓ {len(nodes)} Knoten, {len(edges)} Kanten → {self.out_path}")
        return graph

    def _load_entries(self) -> List[Dict]:
        entries = []
        for cat in CATEGORIES:
            cat_dir = KNOWLEDGE_DIR / cat
            if not cat_dir.exists():
                continue
            for f in sorted(cat_dir.glob("*.md")):
                try:
                    post = fm.load(str(f))
                    entries.append({"meta": post.metadata, "content": post.content, "path": f})
                except Exception:
                    pass
        return entries

    @staticmethod
    def _slugify(text: str) -> str:
        s = text.lower()
        s = re.sub(r"[äÄ]", "ae", s)
        s = re.sub(r"[öÖ]", "oe", s)
        s = re.sub(r"[üÜ]", "ue", s)
        s = re.sub(r"[ß]", "ss", s)
        s = re.sub(r"[^a-z0-9_]+", "_", s)
        return s.strip("_")[:80]


def _infer_rel(src_cat: str, tgt_cat: str) -> str:
    if src_cat == "agencies" and tgt_cat == "people":
        return "employed"
    if src_cat == "people" and tgt_cat == "agencies":
        return "worked_at"
    if src_cat == "agencies" and tgt_cat == "agencies":
        return "competed_with"
    if src_cat == "people" and tgt_cat == "people":
        return "collaborated_with"
    if tgt_cat == "eras":
        return "belongs_to_era"
    if tgt_cat == "philosophy":
        return "exemplifies"
    if tgt_cat == "work":
        return "created"
    if tgt_cat == "scandals":
        return "involved_in"
    return "related"
