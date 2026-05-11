"""Unit tests for the GraphBuilder."""
import sys
import json
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.graph_builder import GraphBuilder
from tools.knowledge_base import KnowledgeBase


@pytest.fixture(scope="module")
def graph():
    """Build the graph once for all tests in this module."""
    kb = KnowledgeBase()
    gb = GraphBuilder(kb)
    return gb.build()


@pytest.fixture(scope="module")
def node_ids(graph):
    return {n["id"] for n in graph["nodes"]}


def test_graph_has_nodes(graph):
    assert len(graph["nodes"]) > 0, "Graph should have at least one node"


def test_graph_has_edges(graph):
    assert len(graph["edges"]) > 0, "Graph should have at least one edge"


def test_graph_node_count_matches_kb(graph):
    kb = KnowledgeBase()
    all_entries = kb.list_all()
    # Allow for up to 5 entries that might fail to parse
    assert len(graph["nodes"]) >= len(all_entries) - 5, (
        f"Graph has {len(graph['nodes'])} nodes but KB has {len(all_entries)} entries"
    )


def test_graph_edge_count_above_minimum(graph):
    """With short-name matching and lowered tag threshold, expect >200 edges."""
    assert len(graph["edges"]) > 200, (
        f"Expected >200 edges for good graph connectivity, got {len(graph['edges'])}"
    )


def test_no_self_loops(graph):
    """No edge should connect a node to itself."""
    self_loops = [
        e for e in graph["edges"]
        if e["source"] == e["target"]
    ]
    assert self_loops == [], f"Found self-loops: {self_loops[:5]}"


def test_no_edges_to_nonexistent_nodes(graph, node_ids):
    """All edge endpoints must refer to nodes that exist in the graph."""
    bad_edges = []
    for e in graph["edges"]:
        src = e["source"] if isinstance(e["source"], str) else e["source"]["id"]
        tgt = e["target"] if isinstance(e["target"], str) else e["target"]["id"]
        if src not in node_ids or tgt not in node_ids:
            bad_edges.append(e)
    assert bad_edges == [], (
        f"Found {len(bad_edges)} edges referencing non-existent nodes: {bad_edges[:3]}"
    )


def test_all_nodes_have_required_fields(graph):
    """Every node must have id, label, type, and color."""
    required = {"id", "label", "type", "color"}
    for node in graph["nodes"]:
        missing = required - set(node.keys())
        assert not missing, f"Node {node.get('id','?')} missing fields: {missing}"


def test_node_ids_are_unique(graph):
    ids = [n["id"] for n in graph["nodes"]]
    assert len(ids) == len(set(ids)), "Duplicate node IDs found in graph"


def test_node_types_are_valid(graph):
    valid_types = {"agency", "person", "era", "work", "concept", "scandal", "life", "technology", "visual"}
    for node in graph["nodes"]:
        assert node["type"] in valid_types, (
            f"Node {node['id']} has invalid type {node['type']!r}"
        )


def test_edges_have_required_fields(graph):
    """Every edge must have source, target, and type."""
    for edge in graph["edges"]:
        assert "source" in edge, f"Edge missing 'source': {edge}"
        assert "target" in edge, f"Edge missing 'target': {edge}"
        assert "type" in edge, f"Edge missing 'type': {edge}"


def test_no_duplicate_edges(graph):
    """No two edges should have the same source+target+type combination."""
    seen = set()
    dupes = []
    for e in graph["edges"]:
        src = e["source"] if isinstance(e["source"], str) else e["source"]["id"]
        tgt = e["target"] if isinstance(e["target"], str) else e["target"]["id"]
        key = f"{src}|{tgt}|{e['type']}"
        rev = f"{tgt}|{src}|{e['type']}"
        if key in seen or rev in seen:
            dupes.append(key)
        seen.add(key)
    assert dupes == [], f"Found {len(dupes)} duplicate edges"


def test_graph_json_written_to_disk():
    """graph.json should exist on disk after build."""
    graph_path = Path(__file__).parent.parent / "wiki" / "graph.json"
    assert graph_path.exists(), "wiki/graph.json does not exist"
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    assert "nodes" in data
    assert "edges" in data


def test_person_nodes_exist(graph):
    person_nodes = [n for n in graph["nodes"] if n["type"] == "person"]
    assert len(person_nodes) > 5, "Expected at least 5 person nodes"


def test_agency_nodes_exist(graph):
    agency_nodes = [n for n in graph["nodes"] if n["type"] == "agency"]
    assert len(agency_nodes) > 10, "Expected at least 10 agency nodes"


def test_node_colors_are_hex(graph):
    """Node colors should be valid CSS hex colors."""
    import re
    hex_pattern = re.compile(r'^#[0-9a-fA-F]{3,8}$')
    for node in graph["nodes"]:
        color = node.get("color", "")
        assert hex_pattern.match(color), (
            f"Node {node['id']} has non-hex color: {color!r}"
        )
