"""Tests for Memory ID validation and generation."""

from pathlib import Path

import pytest

from researchos.utils.exceptions import ValidationError
from researchos.utils.ids import (
    MemoryIdGenerator,
    is_valid_memory_id,
    slugify_project_id,
    validate_memory_id,
)


def test_memory_id_validation():
    assert is_valid_memory_id("MEM-2026-0001")
    assert is_valid_memory_id("MEM-2026-105")
    assert is_valid_memory_id("MEM-2025-0042")

    assert not is_valid_memory_id("INVALID-123")
    assert not is_valid_memory_id("MEM-26-01")
    assert not is_valid_memory_id("PRJ-2026-001")

    year, seq = validate_memory_id("MEM-2026-0042")
    assert year == 2026
    assert seq == 42

    with pytest.raises(ValidationError):
        validate_memory_id("invalid-id")


def test_slugify_project():
    assert slugify_project_id("My Deep Learning Project") == "my-deep-learning-project"
    assert slugify_project_id("LLM_Agent & Memory!") == "llm-agent-memory"
    assert slugify_project_id("   ") == "research-project"


def test_memory_id_generator(tmp_path: Path):
    proj_dir = tmp_path / "test-proj"
    proj_dir.mkdir(parents=True)
    generator = MemoryIdGenerator(proj_dir)

    id1 = generator.next_memory_id(year=2026)
    assert id1 == "MEM-2026-0001"

    id2 = generator.next_memory_id(year=2026)
    assert id2 == "MEM-2026-0002"

    # Verify disk scan fallback: if sequences file is deleted but files exist
    obs_file = proj_dir / "observations" / "MEM-2026-0015.md"
    obs_file.parent.mkdir(parents=True, exist_ok=True)
    obs_file.write_text("# MEM-2026-0015", encoding="utf-8")

    (proj_dir / ".researchos" / "sequences.json").unlink()

    id3 = generator.next_memory_id(year=2026)
    # Next should be max(scanned=15) + 1 = 16
    assert id3 == "MEM-2026-0016"
