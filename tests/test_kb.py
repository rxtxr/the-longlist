"""Unit tests for the KnowledgeBase class."""
import sys
import pytest
import tempfile
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.knowledge_base import KnowledgeBase


@pytest.fixture
def tmp_kb(tmp_path):
    """Create a KnowledgeBase with a temporary root directory."""
    kb = KnowledgeBase(root=tmp_path / "knowledge", obsidian_dir=tmp_path / "obsidian")
    return kb


def test_slug_basic():
    assert KnowledgeBase.slug("David Ogilvy") == "david_ogilvy"


def test_slug_german_chars():
    assert KnowledgeBase.slug("Müller & Söhne") == "mueller_soehne"
    assert KnowledgeBase.slug("straße") == "strasse"
    assert KnowledgeBase.slug("Über") == "ueber"


def test_slug_special_chars():
    slug = KnowledgeBase.slug("BBDO — Batten Barton")
    assert " " not in slug
    assert slug.islower() or slug.isdigit() or "_" in slug


def test_slug_max_length():
    long = "a" * 100
    assert len(KnowledgeBase.slug(long)) <= 80


def test_write_entry_creates_file(tmp_kb):
    path = tmp_kb.write_entry(
        category="people",
        entry_id="test_person",
        title="Test Person — ein Beispiel",
        content="This is a test entry about advertising.",
        metadata={"tags": ["test", "advertising"], "confidence": "high"},
        wave=1,
    )
    assert path.exists()
    assert path.suffix == ".md"


def test_write_entry_returns_path_in_correct_category(tmp_kb):
    path = tmp_kb.write_entry(
        category="agencies",
        entry_id="test_agency",
        title="Test Agency — a test",
        content="Content about the agency.",
        metadata={"tags": ["test"]},
        wave=1,
    )
    assert "agencies" in str(path)


def test_write_entry_invalid_category_falls_back(tmp_kb):
    # Invalid category should fall back to 'agencies'
    path = tmp_kb.write_entry(
        category="nonexistent_cat",
        entry_id="some_entry",
        title="Some Entry",
        content="Content.",
        metadata={},
        wave=0,
    )
    assert path.exists()


def test_read_entry_returns_dict(tmp_kb):
    path = tmp_kb.write_entry(
        category="people",
        entry_id="read_test",
        title="Read Test Person",
        content="Content for reading.",
        metadata={"tags": ["readtest"]},
        wave=0,
    )
    entry = tmp_kb.read_entry(path)
    assert entry is not None
    assert "meta" in entry
    assert "content" in entry
    assert "path" in entry


def test_read_entry_meta_fields(tmp_kb):
    path = tmp_kb.write_entry(
        category="people",
        entry_id="meta_test",
        title="Meta Test",
        content="Content.",
        metadata={"tags": ["tagA", "tagB"], "confidence": "high", "era": "1960-1970"},
        wave=2,
    )
    entry = tmp_kb.read_entry(path)
    assert entry["meta"]["title"] == "Meta Test"
    assert "tagA" in entry["meta"]["tags"]
    assert entry["meta"]["confidence"] == "high"


def test_read_entry_nonexistent_returns_none(tmp_kb):
    result = tmp_kb.read_entry(tmp_kb.root / "people" / "does_not_exist.md")
    assert result is None


def test_get_existing_entry(tmp_kb):
    tmp_kb.write_entry(
        category="agencies",
        entry_id="get_test_agency",
        title="Get Test Agency",
        content="Agency content.",
        metadata={},
        wave=0,
    )
    entry = tmp_kb.get("agencies", "get_test_agency")
    assert entry is not None
    assert entry["meta"]["title"] == "Get Test Agency"


def test_get_missing_entry_returns_none(tmp_kb):
    assert tmp_kb.get("people", "totally_missing") is None


def test_exists_true(tmp_kb):
    tmp_kb.write_entry(
        category="eras",
        entry_id="the_1960s",
        title="The 1960s",
        content="The 60s were big.",
        metadata={},
        wave=0,
    )
    assert tmp_kb.exists("eras", "the_1960s") is True


def test_exists_false(tmp_kb):
    assert tmp_kb.exists("eras", "never_written") is False


def test_list_category_empty(tmp_kb):
    result = tmp_kb.list_category("people")
    assert result == []


def test_list_category_after_writes(tmp_kb):
    for i in range(3):
        tmp_kb.write_entry(
            category="people",
            entry_id=f"person_{i}",
            title=f"Person {i}",
            content=f"Content {i}.",
            metadata={},
            wave=0,
        )
    result = tmp_kb.list_category("people")
    assert len(result) == 3


def test_list_category_returns_correct_type(tmp_kb):
    tmp_kb.write_entry(
        category="agencies",
        entry_id="list_test",
        title="List Test",
        content="Content.",
        metadata={},
        wave=0,
    )
    entries = tmp_kb.list_category("agencies")
    assert isinstance(entries, list)
    assert all(isinstance(e, dict) for e in entries)
    assert all("meta" in e and "content" in e for e in entries)


def test_get_stats_structure(tmp_kb):
    stats = tmp_kb.get_stats()
    assert "total" in stats
    assert isinstance(stats["total"], int)
    # Should have a key per category
    from config import CATEGORIES
    for cat in CATEGORIES:
        assert cat in stats


def test_get_stats_total_matches_sum(tmp_kb):
    from config import CATEGORIES
    for i, cat in enumerate(CATEGORIES[:3]):
        tmp_kb.write_entry(
            category=cat,
            entry_id=f"stats_entry_{i}",
            title=f"Stats Entry {i}",
            content=".",
            metadata={},
            wave=0,
        )
    stats = tmp_kb.get_stats()
    cat_sum = sum(stats[c] for c in CATEGORIES)
    assert stats["total"] == cat_sum


def test_write_preserves_wave_on_rewrite(tmp_kb):
    """Re-writing an entry should preserve the existing wave value."""
    path = tmp_kb.write_entry(
        category="people",
        entry_id="wave_test",
        title="Wave Test",
        content="Original content.",
        metadata={},
        wave=3,
    )
    # Re-write with wave=0 — existing wave should be preserved
    tmp_kb.write_entry(
        category="people",
        entry_id="wave_test",
        title="Wave Test Updated",
        content="Updated content.",
        metadata={},
        wave=0,
    )
    entry = tmp_kb.get("people", "wave_test")
    assert entry["meta"]["wave"] == 3
