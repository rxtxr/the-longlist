"""E2E link integrity tests for the built wiki."""
import sys
import re
import json
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

WIKI_DIR = Path(__file__).parent.parent / "wiki"
KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"

wiki_built = pytest.mark.skipif(
    not (WIKI_DIR / "index.html").exists(),
    reason="Wiki not built — run `python research_room.py --wiki` first"
)


@wiki_built
def test_index_html_exists():
    assert (WIKI_DIR / "index.html").exists()


@wiki_built
def test_graph_html_exists():
    assert (WIKI_DIR / "graph.html").exists()


@wiki_built
def test_assets_exist():
    assert (WIKI_DIR / "assets" / "style.css").exists()
    assert (WIKI_DIR / "assets" / "search.js").exists()


@wiki_built
def test_all_href_links_resolve():
    """All href="*.html" in the wiki must point to existing files."""
    broken = []
    for html_file in WIKI_DIR.rglob("*.html"):
        content = html_file.read_text(encoding="utf-8", errors="replace")
        hrefs = re.findall(r'href="([^"]+\.html)"', content)
        for href in hrefs:
            if href.startswith("http") or href.startswith("//"):
                continue
            # Resolve relative to the html file's directory
            target = (html_file.parent / href).resolve()
            if not target.exists():
                broken.append(f"{html_file.name}: {href} -> {target}")
    assert broken == [], f"Broken links found:\n" + "\n".join(broken[:20])


@wiki_built
def test_css_and_js_links_resolve():
    """All src="*.js" and href="*.css" must resolve to existing files."""
    broken = []
    for html_file in WIKI_DIR.rglob("*.html"):
        content = html_file.read_text(encoding="utf-8", errors="replace")
        # CSS hrefs
        css_refs = re.findall(r'href="([^"]+\.css)"', content)
        # JS srcs
        js_refs = re.findall(r'src="([^"]+\.js)"', content)
        for ref in css_refs + js_refs:
            if ref.startswith("http") or ref.startswith("//"):
                continue
            target = (html_file.parent / ref).resolve()
            if not target.exists():
                broken.append(f"{html_file.name}: {ref}")
    assert broken == [], f"Broken asset links:\n" + "\n".join(broken[:20])


@wiki_built
def test_graph_html_contains_valid_json():
    """graph.html must embed valid graph JSON with >100 nodes."""
    graph_html = (WIKI_DIR / "graph.html").read_text(encoding="utf-8")
    # Extract the G = {...}; assignment
    match = re.search(r'const G = (\{.*?\});', graph_html, re.DOTALL)
    assert match, "Could not find 'const G = ...' in graph.html"
    graph_data = json.loads(match.group(1))
    assert "nodes" in graph_data
    assert "edges" in graph_data
    assert graph_data["nodes"].__len__() > 100, (
        f"Expected >100 nodes in graph, got {len(graph_data['nodes'])}"
    )


@wiki_built
def test_graph_json_file_valid():
    """wiki/graph.json should exist and be valid JSON."""
    graph_path = WIKI_DIR / "graph.json"
    assert graph_path.exists()
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    assert len(data.get("nodes", [])) > 100


@wiki_built
def test_every_kb_entry_has_html_page():
    """Every markdown entry in knowledge/<category>/ should have a corresponding HTML page.
    Files at the root of knowledge/ (like GRAPH.md) are not entries and are skipped.
    """
    from config import CATEGORIES
    missing = []
    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        cat = md_file.parent.name
        # Only check files inside a valid category directory
        if cat not in CATEGORIES:
            continue
        fname = md_file.stem
        expected_html = WIKI_DIR / "pages" / cat / f"{fname}.html"
        if not expected_html.exists():
            missing.append(str(md_file.relative_to(KNOWLEDGE_DIR)))
    assert missing == [], f"Missing HTML pages for:\n" + "\n".join(missing[:20])


@wiki_built
def test_no_unresolved_wikilinks_in_html():
    """No HTML page should contain <em>[[...]]</em> — unresolved wikilinks."""
    bad = []
    for html_file in WIKI_DIR.rglob("*.html"):
        content = html_file.read_text(encoding="utf-8", errors="replace")
        # Look for em tags containing raw wikilink brackets
        if re.search(r'<em>\[\[', content):
            bad.append(html_file.name)
    assert bad == [], f"Files with raw [[wikilinks]] in <em> tags: {bad}"


@wiki_built
def test_wikilink_resolution_rate():
    """At least 50% of [[wikilinks]] in MD files should resolve to links in HTML."""
    # Count total wikilinks in MD
    total_wikilinks = 0
    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8", errors="replace")
        total_wikilinks += len(re.findall(r'\[\[[^\]]+\]\]', content))

    if total_wikilinks == 0:
        pytest.skip("No wikilinks found in knowledge base")

    # Count resolved links in HTML pages (internal page links)
    resolved = 0
    for html_file in (WIKI_DIR / "pages").rglob("*.html"):
        content = html_file.read_text(encoding="utf-8", errors="replace")
        resolved += len(re.findall(r'href="../../pages/[^"]*\.html"', content))

    rate = resolved / total_wikilinks
    assert rate >= 0.50, (
        f"Wikilink resolution rate too low: {rate:.1%} "
        f"({resolved} resolved / {total_wikilinks} total). Expected >= 50%."
    )


@wiki_built
def test_category_pages_exist():
    """Each category should have a listing page."""
    from config import CATEGORIES
    for cat in CATEGORIES:
        cat_page = WIKI_DIR / "pages" / f"{cat}.html"
        # Only check if there are entries in this category
        cat_dir = KNOWLEDGE_DIR / cat
        if cat_dir.exists() and any(cat_dir.glob("*.md")):
            assert cat_page.exists(), f"Missing category page: pages/{cat}.html"


@wiki_built
def test_entry_pages_have_nav_links():
    """Entry pages should contain sidebar navigation links."""
    pages_dir = WIKI_DIR / "pages"
    sample_pages = list(pages_dir.rglob("*.html"))[:10]
    for html_file in sample_pages:
        if html_file.parent == pages_dir:
            continue  # skip category pages
        content = html_file.read_text(encoding="utf-8", errors="replace")
        assert 'class="sidebar"' in content, f"{html_file.name} missing sidebar"


@wiki_built
def test_graph_nav_link_in_entry_pages():
    """Entry pages should have a link to graph.html in the sidebar."""
    pages_dir = WIKI_DIR / "pages"
    entry_pages = [
        f for f in pages_dir.rglob("*.html")
        if f.parent != pages_dir  # Skip category-level pages
    ]
    assert len(entry_pages) > 0, "No entry pages found"
    # Check a sample
    sample = entry_pages[:5]
    for html_file in sample:
        content = html_file.read_text(encoding="utf-8", errors="replace")
        assert 'graph.html' in content, (
            f"{html_file.name} does not contain a link to graph.html"
        )


@wiki_built
def test_entry_pages_have_breadcrumb():
    """Entry pages should contain breadcrumb navigation."""
    pages_dir = WIKI_DIR / "pages"
    entry_pages = [
        f for f in pages_dir.rglob("*.html")
        if f.parent != pages_dir
    ][:5]
    for html_file in entry_pages:
        content = html_file.read_text(encoding="utf-8", errors="replace")
        assert 'class="breadcrumb"' in content, (
            f"{html_file.name} missing breadcrumb"
        )
