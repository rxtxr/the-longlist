"""Unit tests for the title index / wikilink resolver in WikiBuilder."""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.wiki_builder import WikiBuilder
from tools.knowledge_base import KnowledgeBase


def make_entry(fname, title, tags=None, cat="agencies"):
    """Helper to build a mock entry dict."""
    return {
        "meta": {"title": title, "tags": tags or []},
        "path": Path(f"/fake/{cat}/{fname}.md"),
    }


@pytest.fixture
def test_entries():
    return {
        "david_ogilvy_der_werbe_guru": make_entry(
            "david_ogilvy_der_werbe_guru",
            "David Ogilvy — der Werbe-Guru",
            tags=["David Ogilvy", "Ogilvy"],
            cat="people",
        ),
        "bbdo_batten_barton_durstine_osborn": make_entry(
            "bbdo_batten_barton_durstine_osborn",
            "BBDO — Batten Barton Durstine & Osborn",
            tags=["BBDO", "Werbeagentur"],
            cat="agencies",
        ),
        "leo_burnett_der_chicagoer_geschichtenerzaehler": make_entry(
            "leo_burnett_der_chicagoer_geschichtenerzaehler",
            "Leo Burnett — der Chicagoer Geschichtenerzähler",
            tags=["Leo Burnett"],
            cat="people",
        ),
        "doyle_dane_bernbach_ddb_die_creative_revolution": make_entry(
            "doyle_dane_bernbach_ddb_die_creative_revolution",
            "Doyle Dane Bernbach (DDB) — die Creative Revolution",
            tags=["DDB", "Creative Revolution"],
            cat="agencies",
        ),
        "saatchi_saatchi_thatcherisierung_der_werbung": make_entry(
            "saatchi_saatchi_thatcherisierung_der_werbung",
            "Saatchi & Saatchi — Thatcherisierung der Werbung",
            tags=["Saatchi", "London"],
            cat="agencies",
        ),
        "die_geschichte_der_deutschen_werbeagentur_scholz_friends": make_entry(
            "die_geschichte_der_deutschen_werbeagentur_scholz_friends",
            "Die Geschichte der deutschen Werbeagentur Scholz & Friends (gegründet 1981)",
            tags=["german-advertising"],
            cat="agencies",
        ),
        "bill_bernbach_vater_der_kreativen_revolution": make_entry(
            "bill_bernbach_vater_der_kreativen_revolution",
            "Bill Bernbach — Vater der Kreativen Revolution",
            tags=["Bill Bernbach"],
            cat="people",
        ),
        "ogilvy_mather": make_entry(
            "ogilvy_mather",
            "Ogilvy & Mather — David Ogilvys Agenturprinzipien",
            tags=["Ogilvy", "Ogilvy & Mather"],
            cat="agencies",
        ),
    }


@pytest.fixture
def wb():
    kb = KnowledgeBase()
    return WikiBuilder(kb)


@pytest.fixture
def index(wb, test_entries):
    return wb._build_title_index(test_entries)


# ─── Short-name resolution tests ───


def test_short_name_david_ogilvy(index):
    """'David Ogilvy' should match 'David Ogilvy — der Werbe-Guru'."""
    result = index.get("david ogilvy")
    assert result is not None, "'David Ogilvy' not found in index"
    assert "david_ogilvy" in result[1], f"Wrong match: {result}"


def test_short_name_bbdo(index):
    """'BBDO' should match 'BBDO — Batten Barton Durstine & Osborn'."""
    result = index.get("bbdo")
    assert result is not None, "'BBDO' not found in index"
    assert "bbdo_batten_barton" in result[1]


def test_short_name_leo_burnett(index):
    """'Leo Burnett' should match 'Leo Burnett — der Chicagoer Geschichtenerzähler'."""
    result = index.get("leo burnett")
    assert result is not None, "'Leo Burnett' not found"
    assert "leo_burnett" in result[1]


def test_doyle_dane_bernbach_no_paren(index):
    """'Doyle Dane Bernbach' (without DDB abbreviation) should resolve."""
    result = index.get("doyle dane bernbach")
    assert result is not None, "'Doyle Dane Bernbach' not found"
    assert "doyle_dane_bernbach" in result[1]


def test_bill_bernbach(index):
    """'Bill Bernbach' should resolve via short name."""
    result = index.get("bill bernbach")
    assert result is not None, "'Bill Bernbach' not found"


def test_saatchi_short(index):
    """'Saatchi & Saatchi' should resolve via short name."""
    result = index.get("saatchi & saatchi")
    assert result is not None, "'Saatchi & Saatchi' not found"


# ─── Full title resolution ───


def test_full_title_resolves(index):
    full = "David Ogilvy — der Werbe-Guru".lower()
    result = index.get(full)
    assert result is not None, "Full title not in index"


def test_full_title_with_parens(index):
    """Full title with parenthetical abbreviation should resolve."""
    full = "Doyle Dane Bernbach (DDB) — die Creative Revolution".lower()
    result = index.get(full)
    assert result is not None, "Full title with parens not in index"


# ─── Slug/ID resolution ───


def test_slug_id_resolves(index):
    """The file stem (slug) should always resolve."""
    result = index.get("david_ogilvy_der_werbe_guru")
    assert result is not None, "Slug ID not in index"


def test_slug_id_bbdo_resolves(index):
    result = index.get("bbdo_batten_barton_durstine_osborn")
    assert result is not None, "BBDO slug not in index"


# ─── Tag-based resolution ───


def test_tag_alias_david_ogilvy(index):
    """Tag 'David Ogilvy' should serve as an alias."""
    result = index.get("david ogilvy")  # tag is "David Ogilvy"
    assert result is not None


def test_tag_alias_ddb(index):
    """Tag 'DDB' should resolve to the DDB entry."""
    result = index.get("ddb")
    assert result is not None, "Tag-based 'DDB' not found"
    assert "doyle_dane_bernbach" in result[1]


# ─── Descriptive title stripping ───


def test_scholz_and_friends_extracted_from_long_title(index):
    """'Scholz & Friends' should be extractable from the long descriptive title."""
    result = index.get("scholz & friends")
    assert result is not None, (
        "'Scholz & Friends' not resolved from long descriptive title. "
        "The title index should strip German article/descriptive prefixes."
    )


# ─── Integration with actual KB ───


def test_real_kb_index_has_david_ogilvy():
    """Integration test: real KB index resolves 'David Ogilvy'."""
    kb = KnowledgeBase()
    entries = kb.list_all()
    entries_map = {e["path"].stem: e for e in entries}
    wb = WikiBuilder(kb)
    idx = wb._build_title_index(entries_map)
    assert "david ogilvy" in idx, "Real KB index missing 'David Ogilvy'"


def test_real_kb_index_has_bbdo():
    """Integration test: real KB index resolves 'BBDO'."""
    kb = KnowledgeBase()
    entries = kb.list_all()
    entries_map = {e["path"].stem: e for e in entries}
    wb = WikiBuilder(kb)
    idx = wb._build_title_index(entries_map)
    assert "bbdo" in idx, "Real KB index missing 'BBDO'"


def test_real_kb_index_has_leo_burnett():
    """Integration test: real KB index resolves 'Leo Burnett'."""
    kb = KnowledgeBase()
    entries = kb.list_all()
    entries_map = {e["path"].stem: e for e in entries}
    wb = WikiBuilder(kb)
    idx = wb._build_title_index(entries_map)
    assert "leo burnett" in idx, "Real KB index missing 'Leo Burnett'"


def test_real_kb_index_has_bill_bernbach():
    """Integration test: real KB index resolves 'Bill Bernbach'."""
    kb = KnowledgeBase()
    entries = kb.list_all()
    entries_map = {e["path"].stem: e for e in entries}
    wb = WikiBuilder(kb)
    idx = wb._build_title_index(entries_map)
    assert "bill bernbach" in idx, "Real KB index missing 'Bill Bernbach'"


def test_real_kb_index_has_saatchi():
    """Integration test: real KB index resolves 'Saatchi & Saatchi'."""
    kb = KnowledgeBase()
    entries = kb.list_all()
    entries_map = {e["path"].stem: e for e in entries}
    wb = WikiBuilder(kb)
    idx = wb._build_title_index(entries_map)
    assert "saatchi & saatchi" in idx, "Real KB index missing 'Saatchi & Saatchi'"


def test_real_kb_index_size():
    """Index should be significantly larger than number of entries (multiple aliases per entry)."""
    kb = KnowledgeBase()
    entries = kb.list_all()
    entries_map = {e["path"].stem: e for e in entries}
    wb = WikiBuilder(kb)
    idx = wb._build_title_index(entries_map)
    # Index should have at least 2x as many keys as entries (each gets several aliases)
    assert len(idx) >= len(entries) * 2, (
        f"Index has only {len(idx)} keys for {len(entries)} entries — expected >= {len(entries)*2}"
    )
