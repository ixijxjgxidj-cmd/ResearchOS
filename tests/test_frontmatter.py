"""Tests for YAML frontmatter parsing, dumping, and atomic writing."""

from pathlib import Path
from researchos.storage.atomic_writer import atomic_write_text
from researchos.storage.frontmatter import dump_frontmatter, parse_frontmatter


def test_frontmatter_parse_and_dump():
    meta = {
        "schema_version": 1,
        "id": "PRJ-2026-001",
        "name": "Test Project",
        "status": "active",
        "members": ["agent1", "agent2"],
    }
    body = "# Test Project\n\n## Background\nSome background info."

    raw = dump_frontmatter(meta, body)
    assert raw.startswith("---\n")
    assert "schema_version: 1" in raw
    assert "id: PRJ-2026-001" in raw
    assert "# Test Project" in raw

    parsed_meta, parsed_body = parse_frontmatter(raw)
    assert parsed_meta["id"] == "PRJ-2026-001"
    assert parsed_meta["members"] == ["agent1", "agent2"]
    assert "# Test Project" in parsed_body
    assert "Some background info." in parsed_body


def test_atomic_write_text(tmp_path: Path):
    target = tmp_path / "subdir" / "test.txt"
    written_path = atomic_write_text(target, "hello atomic world")
    assert written_path.exists()
    assert written_path.read_text(encoding="utf-8") == "hello atomic world"
