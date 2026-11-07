"""Tests for v1 to v2 migration tool."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from researchos.core.project_service import ProjectService
from researchos.core.storage_service import atomic_write_text, dump_frontmatter
from scripts.migrate_v1_to_v2 import run_migration


def test_v1_to_v2_migration(tmp_path: Path):
    v1_vault = tmp_path / "v1_vault"
    v2_vault = tmp_path / "v2_vault"

    # Setup old v1 structure
    p_dir = v1_vault / "00-Projects" / "PRJ-2026-001"
    for sub in ("Findings", "Runs", "Experiments", "Claims", "Decisions", "Artifacts"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)
    (v1_vault / "01-Literature").mkdir(parents=True, exist_ok=True)

    # Write old PROJECT.md
    proj_meta = {
        "id": "PRJ-2026-001",
        "name": "Legacy LLM Scaling Project",
        "scope": "Explore batch size scaling",
        "research_question": "Does batch size 1024 improve throughput?",
        "status": "active",
        "objectives": ["scaling", "throughput"],
    }
    atomic_write_text(p_dir / "PROJECT.md", dump_frontmatter(proj_meta, "# Legacy LLM Scaling Project"))
    atomic_write_text(p_dir / "STATUS.md", "# Status\nActive roadmap.\n")
    atomic_write_text(p_dir / "HANDOFF.md", "# Handoff\nFinished step 1.\n")

    # Write old finding
    find_meta = {
        "id": "FIND-2026-001",
        "title": "Throughput increases linearly up to BS=512",
        "tags": ["scaling"],
        "agent_name": "agent-v1",
    }
    atomic_write_text(p_dir / "Findings" / "FIND-2026-001.md", dump_frontmatter(find_meta, "Details of throughput finding."))

    # Write old literature paper
    paper_meta = {
        "id": "PAPER-2026-001",
        "title": "Attention Is All You Need",
        "tags": ["transformer"],
        "projects": ["PRJ-2026-001"],
    }
    atomic_write_text(v1_vault / "01-Literature" / "PAPER-2026-001.md", dump_frontmatter(paper_meta, "Vaswani et al. 2017."))

    # 1. Test Dry Run
    dry_report = run_migration(vault_root=v1_vault, target_root=v2_vault, apply=False)
    assert dry_report["dry_run"] is True
    assert dry_report["backup_path"] is None
    assert dry_report["entities_migrated"]["projects"] == 1
    assert dry_report["entities_migrated"]["observations"] >= 1
    assert not (v2_vault / "PRJ-2026-001").exists()

    # 2. Test Real Apply Migration
    apply_report = run_migration(vault_root=v1_vault, target_root=v2_vault, apply=True)
    assert apply_report["dry_run"] is False
    assert apply_report["backup_path"] is not None
    assert Path(apply_report["backup_path"]).exists()

    # Verify v2 structure
    ps2 = ProjectService(v2_vault)
    p2 = ps2.get_project("PRJ-2026-001")
    assert p2.project_name == "Legacy LLM Scaling Project"

    val = ps2.validate_project("PRJ-2026-001")
    assert val["valid"] is True
    assert val["total_memories"] >= 2  # finding + paper reference

    # Verify original records still intact (no deletion)
    assert (p_dir / "Findings" / "FIND-2026-001.md").exists()
    assert (v1_vault / "01-Literature" / "PAPER-2026-001.md").exists()
