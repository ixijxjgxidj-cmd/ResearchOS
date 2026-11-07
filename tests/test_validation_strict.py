"""Tests for project integrity validation, broken links, duplicate IDs, and invalid relations."""

from pathlib import Path

from researchos.core.memory_service import MemoryService
from researchos.core.project_service import ProjectService
from researchos.models.memory import MemoryType


def test_validate_project_broken_links_strict(tmp_path: Path):
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Validation Test", project_id="val-proj")
    ms = MemoryService(vault)

    # Add memory with broken relative markdown link
    ms.add_memory(
        project_id="val-proj",
        type=MemoryType.OBSERVATION,
        title="Observation with broken link",
        content="See detailed metrics in [NonExistentReport](../reports/missing.md).",
    )

    # In strict mode, valid must be False
    res_strict = ps.validate_project("val-proj", strict=True)
    assert res_strict["valid"] is False
    assert len(res_strict["broken_links"]) >= 1
    assert "missing.md" in res_strict["broken_links"][0]["message"]

    # In non-strict mode, valid is True (broken links treated as warnings)
    res_lenient = ps.validate_project("val-proj", strict=False)
    assert res_lenient["valid"] is True
    assert len(res_lenient["broken_links"]) >= 1


def test_validate_duplicate_ids_and_invalid_relations(tmp_path: Path):
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Integrity Check", project_id="int-proj")
    ms = MemoryService(vault)

    # Add memory with invalid relation to phantom memory ID
    ms.add_memory(
        project_id="int-proj",
        type=MemoryType.DECISION,
        title="Valid Decision",
        content="Testing relation validity.",
        related_memory_ids=["MEM-2099-9999"],
    )

    res = ps.validate_project("int-proj", strict=True)
    assert res["valid"] is False
    assert len(res["invalid_relations"]) >= 1
    assert res["invalid_relations"][0]["target_id"] == "MEM-2099-9999"


def test_validate_clean_project(tmp_path: Path):
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Clean Project", project_id="clean-proj")
    ms = MemoryService(vault)

    ms.add_memory(
        project_id="clean-proj",
        type=MemoryType.KNOWLEDGE,
        title="Clean Concept",
        content="Fully self-contained memory.",
    )

    res = ps.validate_project("clean-proj", strict=True)
    assert res["valid"] is True
    assert res["total_memories"] == 1
    assert len(res["errors"]) == 0
    assert len(res["broken_links"]) == 0
    assert len(res["invalid_relations"]) == 0
