"""HTTP-Server-Test: validiert dass alle Assets und Seiten korrekt über HTTP erreichbar sind.
Simuliert exakt was ein Browser macht — kein file://-Fallstrick."""
import json
import re
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

import pytest

WIKI_DIR = Path(__file__).parent.parent / "wiki"
PORT = 18765


@pytest.fixture(scope="module")
def server():
    """Startet einen HTTP-Server im wiki/-Verzeichnis für alle Tests dieses Moduls."""
    if not (WIKI_DIR / "index.html").exists():
        pytest.skip("wiki/ nicht gebaut — bitte 'python research_room.py --wiki' ausführen")

    handler = _make_handler(WIKI_DIR)
    httpd = HTTPServer(("127.0.0.1", PORT), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)
    yield f"http://127.0.0.1:{PORT}"
    httpd.shutdown()


def _make_handler(directory):
    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(directory), **kw)
        def log_message(self, *_):
            pass  # kein Log-Spam
    return H


def get(server_url, path):
    url = f"{server_url}/{path.lstrip('/')}"
    with urlopen(url, timeout=5) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


# ── Kern-Assets ─────────────────────────────────────────────────────────────

def test_index_html_ok(server):
    status, body = get(server, "index.html")
    assert status == 200
    assert "<html" in body

def test_css_loads(server):
    status, body = get(server, "assets/style.css")
    assert status == 200, "style.css nicht erreichbar — Sidebar/Layout bricht ohne CSS"
    assert len(body) > 500, "CSS-Datei verdächtig leer"
    assert "--bg:" in body or "--accent:" in body, "CSS-Custom-Properties fehlen"

def test_search_js_loads(server):
    status, body = get(server, "assets/search.js")
    assert status == 200, "search.js nicht erreichbar — Suche funktioniert nicht"
    assert len(body) > 50

def test_d3_loads(server):
    status, body = get(server, "assets/d3.v7.min.js")
    assert status == 200, "D3.js nicht erreichbar — Wissensgraph bleibt leer"
    assert len(body) > 100_000, "D3.js-Datei zu klein, möglicherweise beschädigt"

def test_graph_html_loads(server):
    status, body = get(server, "graph.html")
    assert status == 200
    assert "d3.v7.min.js" in body, "graph.html referenziert D3 nicht"
    assert "assets/style.css" in body

# ── Seiten-Struktur ──────────────────────────────────────────────────────────

def test_category_pages_load(server):
    from config import CATEGORIES
    for cat in CATEGORIES:
        status, _ = get(server, f"pages/{cat}.html")
        assert status == 200, f"Kategorie-Seite pages/{cat}.html nicht erreichbar"

def test_entry_pages_load(server):
    """Stichprobe: erste Seite jeder Kategorie muss laden."""
    for cat_dir in sorted(WIKI_DIR.glob("pages/*")):
        if not cat_dir.is_dir():
            continue
        pages = sorted(cat_dir.glob("*.html"))
        if not pages:
            continue
        fname = pages[0].name
        status, body = get(server, f"pages/{cat_dir.name}/{fname}")
        assert status == 200, f"pages/{cat_dir.name}/{fname} → {status}"
        assert "assets/style.css" in body, f"{fname}: CSS-Link fehlt"
        assert "graph.html" in body, f"{fname}: Wissensgraph-Link fehlt"

def test_entry_page_css_path_correct(server):
    """Entry-Pages liegen 2 Ebenen tief — CSS-Pfad muss ../../assets/style.css sein."""
    for cat_dir in sorted(WIKI_DIR.glob("pages/*")):
        if not cat_dir.is_dir():
            continue
        pages = sorted(cat_dir.glob("*.html"))
        if not pages:
            continue
        _, body = get(server, f"pages/{cat_dir.name}/{pages[0].name}")
        assert "../../assets/style.css" in body, \
            f"{pages[0].name}: falscher CSS-Pfad (erwartet '../../assets/style.css')"
        break  # eine Kategorie reicht als Repräsentant

def test_no_raw_wikilinks_in_html(server):
    """Keine ungeparsten [[...]] in gerenderten Entry-Pages."""
    raw_count = 0
    for cat_dir in sorted(WIKI_DIR.glob("pages/*")):
        if not cat_dir.is_dir():
            continue
        for page in sorted(cat_dir.glob("*.html"))[:3]:
            _, body = get(server, f"pages/{cat_dir.name}/{page.name}")
            raw_count += len(re.findall(r"\[\[", body))
    assert raw_count == 0, f"{raw_count} ungeparste [[wikilinks]] in HTML gefunden"

def test_graph_json_valid(server):
    status, body = get(server, "graph.json")
    assert status == 200
    data = json.loads(body)
    assert len(data["nodes"]) >= 100, "Zu wenige Knoten im Graph"
    assert len(data["edges"]) >= 50,  "Zu wenige Kanten — Graph kaum vernetzt"

def test_all_local_hrefs_resolve(server):
    """Alle href=*.html in index.html müssen 200 zurückgeben."""
    _, index_body = get(server, "index.html")
    hrefs = re.findall(r'href="(pages/[^"]+\.html)"', index_body)
    assert hrefs, "Keine Entry-Links in index.html gefunden"
    broken = []
    for href in hrefs:
        try:
            status, _ = get(server, href)
            if status != 200:
                broken.append((href, status))
        except Exception as e:
            broken.append((href, str(e)))
    assert not broken, f"Kaputte Links in index.html: {broken[:5]}"
