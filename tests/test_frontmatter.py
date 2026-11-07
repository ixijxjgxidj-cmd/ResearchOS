"""Tests for YAML frontmatter parsing, dumping, and atomic writing."""

from pathlib import Path

from researchos.core.storage_service import (
    atomic_write_text,
    dump_frontmatter,
    parse_frontmatter,
)


def test_frontmatter_parse_and_dump():
    meta = {
        "id": "MEM-2026-0001",
        "project_id": "test-proj",
        "type": "knowledge",
        "title": "Test Memory",
        "status": "active",
        "tags": ["agent1", "agent2"],
    }
    body = "# Test Memory\n\n## Background\nSome background info."

    raw = dump_frontmatter(meta, body)
    assert raw.startswith("---\n")
    assert "id: MEM-2026-0001" in raw
    assert "# Test Memory" in raw

    parsed_meta, parsed_body = parse_frontmatter(raw)
    assert parsed_meta["id"] == "MEM-2026-0001"
    assert parsed_meta["tags"] == ["agent1", "agent2"]
    assert "# Test Memory" in parsed_body
    assert "Some background info." in parsed_body


def test_atomic_write_text(tmp_path: Path):
    target = tmp_path / "subdir" / "test.txt"
    written_path = atomic_write_text(target, "hello atomic world")
    assert written_path.exists()
    assert written_path.read_text(encoding="utf-8") == "hello atomic world"
