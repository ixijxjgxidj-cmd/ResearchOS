"""Tests for Project creation, vault structure, status metrics, and dashboards."""

from pathlib import Path
from researchos.core.enums import ProjectStatus
from researchos.services.project_service import ProjectService


def test_init_vault_and_create_project(vault_dir: Path, project_service: ProjectService):
    # Verify directory structure
    assert (vault_dir / "00-Projects").exists()
    assert (vault_dir / "01-Literature").exists()
    assert (vault_dir / "99-Dashboard").exists()
    assert (vault_dir / ".researchos").exists()

    # Create project
    proj = project_service.create_project(
        name="Neural Network Robustness Study",
        research_question="Does adversarial training preserve out-of-distribution generalization?",
        objectives=["Benchmark FGSM and PGD", "Evaluate CIFAR-10-C robustness"],
    )

    assert proj.id.startswith("PRJ-")
    assert proj.status == ProjectStatus.ACTIVE
    assert len(proj.objectives) == 2

    # Check files on disk
    proj_dir = vault_dir / "00-Projects" / proj.id
    assert (proj_dir / "PROJECT.md").exists()
    assert (proj_dir / "STATUS.md").exists()
    assert (proj_dir / "HANDOFF.md").exists()
    assert (proj_dir / "CHANGELOG.md").exists()
    assert (proj_dir / "Experiments").is_dir()
    assert (proj_dir / "Runs").is_dir()

    # Verify H1 title reflects pending status with （未结项）
    proj_content = (proj_dir / "PROJECT.md").read_text(encoding="utf-8")
    assert f"# {proj.name}（未结项）" in proj_content

    # Check project status
    status = project_service.get_project_status(proj.id)
    assert status["name"] == proj.name
    assert status["experiments_count"] == 0

    # Verify dashboards generated
    dash_dir = vault_dir / "99-Dashboard"
    assert (dash_dir / "Projects.md").exists()
    assert proj.id in (dash_dir / "Projects.md").read_text(encoding="utf-8")
