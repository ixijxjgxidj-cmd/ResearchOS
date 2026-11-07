"""Tests for ID validation and generation."""

import pytest
from pathlib import Path
from researchos.core.enums import IdPrefix
from researchos.core.exceptions import ValidationError
from researchos.core.ids import IdGenerator, is_valid_id, validate_id


def test_id_validation():
    assert is_valid_id("PRJ-2026-001")
    assert is_valid_id("EXP-2026-105")
    assert is_valid_id("RUN-2026-002")
    assert is_valid_id("PAPER-2026-001")
    assert is_valid_id("FIND-2026-001")
    assert is_valid_id("CLAIM-2026-001")
    assert is_valid_id("ART-2026-001")
    assert is_valid_id("DEC-2026-001")

    assert not is_valid_id("INVALID-123")
    assert not is_valid_id("PRJ-26-01")
    assert not is_valid_id("EXP-2026-01")

    prefix, year, seq = validate_id("EXP-2026-042")
    assert prefix == "EXP"
    assert year == 2026
    assert seq == 42

    with pytest.raises(ValidationError):
        validate_id("invalid-id")


def test_id_generator(tmp_path: Path):
    generator = IdGenerator(tmp_path)
    id1 = generator.generate_id(IdPrefix.PROJECT, year=2026)
    assert id1 == "PRJ-2026-001"

    id2 = generator.generate_id(IdPrefix.PROJECT, year=2026)
    assert id2 == "PRJ-2026-002"

    exp1 = generator.generate_id(IdPrefix.EXPERIMENT, year=2026)
    assert exp1 == "EXP-2026-001"

    # Verify disk scan fallback: if sequences file is deleted but files exist
    exp_file = tmp_path / "00-Projects" / id1 / "Experiments" / "EXP-2026-005.md"
    exp_file.parent.mkdir(parents=True, exist_ok=True)
    exp_file.write_text("# EXP-2026-005")

    (tmp_path / ".researchos" / "sequences.json").unlink()

    exp2 = generator.generate_id(IdPrefix.EXPERIMENT, year=2026)
    # Next should be max(scanned=5) + 1 = 6
    assert exp2 == "EXP-2026-006"
