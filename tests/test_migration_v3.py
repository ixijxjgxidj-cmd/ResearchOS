"""Tests for ResearchOS v2 to v3 Lossless Migration."""

import json
from pathlib import Path
import pytest
from typer.testing import CliRunner

from researchos.core.memory_service import MemoryService
from researchos.core.project_service import ProjectService
from researchos.interfaces.cli.main import app
from researchos.models.memory import MemoryType
from scripts.migrate_v2_to_v3 import run_migration_v2_to_v3

runner = CliRunner()


@pytest.fixture
def v2_project(tmp_path: Path):
    vault_dir = tmp_path / "ResearchVault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    ps = ProjectService(vault_dir)
    ms = MemoryService(vault_dir)

    ps.create_project(
        name="V2 Legacy Project",
        project_id="legacy-v2-proj",
        research_goal="Test v2 to v3 migration workflow",
    )

    m1 = ms.add_memory(
        project_id="legacy-v2-proj",
        type=MemoryType.DECISION,
        title="Original Arch Choice",
        content="Decided to use ResNet-50 baseline.",
        source_agent="Agent-Old",
    )

    m2 = ms.add_memory(
        project_id="legacy-v2-proj",
        type=MemoryType.OBSERVATION,
        title="Baseline Accuracy",
        content="Achieved 78.5% Top-1 accuracy.",
        source_agent="Agent-Old",
    )

    # Simulate custom notes in existing MEMORY.md
    p_dir = vault_dir / "legacy-v2-proj"
    mem_path = p_dir / "MEMORY.md"
    current_content = mem_path.read_text(encoding="utf-8")
    custom_content = current_content + "\n<!-- RESEARCHOS_CUSTOM_NOTES_START -->\n- [Custom Note]: Manual cluster flag `--qos=high`\n<!-- RESEARCHOS_CUSTOM_NOTES_END -->\n"
    mem_path.write_text(custom_content, encoding="utf-8")

    return {
        "vault_dir": vault_dir,
        "ps": ps,
        "ms": ms,
        "pid": "legacy-v2-proj",
        "m1": m1,
        "m2": m2,
    }


def test_migration_dry_run_leaves_files_untouched(v2_project):
    vault_dir = v2_project["vault_dir"]
    pid = v2_project["pid"]
    p_dir = vault_dir / pid

    mem_before = (p_dir / "MEMORY.md").read_text(encoding="utf-8")

    report = run_migration_v2_to_v3(vault_root=vault_dir, target_project_id=pid, dry_run=True)

    assert report["success"] is True
    assert report["dry_run"] is True
    assert report["summary"]["migrated"] == 1
    assert report["projects"][pid]["status"] == "dry_run_validated"

    # Confirm files were untouched
    mem_after = (p_dir / "MEMORY.md").read_text(encoding="utf-8")
    assert mem_before == mem_after

    # No pre-migration backup folder should have been created
    pre_migration_dirs = list(p_dir.glob(".researchos/backups/pre_v3_migration_*"))
    assert len(pre_migration_dirs) == 0


def test_migration_executes_successfully_and_preserves_everything(v2_project):
    vault_dir = v2_project["vault_dir"]
    pid = v2_project["pid"]
    p_dir = vault_dir / pid

    report = run_migration_v2_to_v3(vault_root=vault_dir, target_project_id=pid, dry_run=False)

    assert report["success"] is True
    assert report["summary"]["migrated"] == 1
    assert report["projects"][pid]["status"] == "success"

    # 1. Pre-migration backup created
    backups_dir = p_dir / ".researchos" / "backups"
    assert backups_dir.exists()
    pre_migration_dirs = [d for d in backups_dir.iterdir() if d.is_dir() and d.name.startswith("pre_v3_migration_")]
    assert len(pre_migration_dirs) == 1
    assert (pre_migration_dirs[0] / "MEMORY.md").exists()

    # 2. records/ directory exists
    assert (p_dir / "records").exists()

    # 3. MEMORY.md upgraded to v3 standard format with custom notes preserved
    new_mem = (p_dir / "MEMORY.md").read_text(encoding="utf-8")
    assert "# MEMORY" in new_mem
    assert "STABLE MEMORY" in new_mem
    assert "WORKING MEMORY" in new_mem
    assert "CRITICAL WARNINGS" in new_mem
    assert "MEMORY POINTERS" in new_mem
    assert "--qos=high" in new_mem

    # 4. Migration map saved
    map_file = p_dir / ".researchos" / "migration_map.json"
    assert map_file.exists()
    map_data = json.loads(map_file.read_text(encoding="utf-8"))
    assert map_data["total_memories"] == 2

    # 5. 100% memory retention
    ms: MemoryService = v2_project["ms"]
    m1_retrieved = ms.get_memory(pid, v2_project["m1"].id)
    assert m1_retrieved.title == "Original Arch Choice"


def test_migration_rollback_on_failure(v2_project, monkeypatch):
    vault_dir = v2_project["vault_dir"]
    pid = v2_project["pid"]
    p_dir = vault_dir / pid

    mem_before = (p_dir / "MEMORY.md").read_text(encoding="utf-8")

    # Simulate failure in rebuild_index
    def mock_rebuild_index_fail(*args, **kwargs):
        raise RuntimeError("Simulated disk error during index rebuild")

    monkeypatch.setattr(ProjectService, "rebuild_index", mock_rebuild_index_fail)

    report = run_migration_v2_to_v3(vault_root=vault_dir, target_project_id=pid, dry_run=False)

    assert report["success"] is False
    assert report["projects"][pid]["status"] == "rolled_back"

    # File was restored from backup
    mem_after = (p_dir / "MEMORY.md").read_text(encoding="utf-8")
    assert mem_after == mem_before


def test_cli_migrate_command(v2_project, monkeypatch):
    vault_dir = v2_project["vault_dir"]
    monkeypatch.setenv("RESEARCH_VAULT_ROOT", str(vault_dir))

    # Test CLI dry run
    result_dry = runner.invoke(app, ["migrate", "--dry-run", "--project", "legacy-v2-proj"])
    assert result_dry.exit_code == 0
    assert "Migration Completed" in result_dry.stdout or "dry_run" in result_dry.stdout.lower()
