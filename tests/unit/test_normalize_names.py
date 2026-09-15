"""Unit tests for author name coercion / normalisation."""

from __future__ import annotations

from paper_intelligence.normalize.names import (
    authors_to_rows,
    coerce_author_entries,
    normalize_author_name,
)


def test_normalize_collapses_whitespace_preserves_unicode() -> None:
    assert normalize_author_name("  张  伟  ") == "张 伟"
    assert normalize_author_name("José\tMaría") == "José María"
    assert normalize_author_name("Александр Пушкин") == "Александр Пушкин"


def test_coerce_empty_does_not_raise() -> None:
    assert coerce_author_entries(None) == []
    assert coerce_author_entries([]) == []
    assert coerce_author_entries("   ") == []
    assert authors_to_rows(None) == []


def test_coerce_string_array() -> None:
    assert coerce_author_entries(["Ada Lovelace", "  Alan Turing "]) == [
        "Ada Lovelace",
        "Alan Turing",
    ]


def test_coerce_object_entries() -> None:
    raw = [{"name": "Grace Hopper"}, {"fullname": "  Katherine Johnson "}]
    assert coerce_author_entries(raw) == ["Grace Hopper", "Katherine Johnson"]


def test_authors_to_rows_positions_and_identity_absent() -> None:
    rows = authors_to_rows(["  Pengrui Quan ", "王小明"])
    assert rows == [
        {
            "author_position": 1,
            "raw_name": "Pengrui Quan",
            "normalized_name": "Pengrui Quan",
        },
        {
            "author_position": 2,
            "raw_name": "王小明",
            "normalized_name": "王小明",
        },
    ]
    for row in rows:
        assert "person_id" not in row
