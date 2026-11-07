"""Project management service and vault lifecycle administration."""

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
from typing import Any

from researchos.core.enums import (
    ExperimentStatus,
    IdPrefix,
    PaperReadingStatus,
    ProjectStatus,
)
from researchos.core.exceptions import (
    EntityNotFoundError,
    ValidationError,
)
from researchos.core.ids import IdGenerator, validate_id
from researchos.core.models import (
    Experiment,
    Paper,
    Project,
    utc_now,
)
from researchos.storage.atomic_writer import atomic_write_text
from researchos.storage.frontmatter import dump_frontmatter
from researchos.storage.link_resolver import format_markdown_link
from researchos.storage.markdown_store import MarkdownStore


class ProjectService:
    """Manages project lifecycles, vault initialization, and dashboard regeneration."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.store = MarkdownStore(self.vault_root)
        self.id_gen = IdGenerator(self.vault_root)

    def init_vault(self) -> dict[str, str]:
        """Initializes a complete ResearchVault filesystem structure."""
        dirs = [
            self.vault_root / ".researchos" / "locks",
            self.vault_root / "00-Projects",
            self.vault_root / "01-Literature",
            self.vault_root / "02-Knowledge" / "Methods",
            self.vault_root / "02-Knowledge" / "Theories",
            self.vault_root / "02-Knowledge" / "Datasets",
            self.vault_root / "03-Protocols",
            self.vault_root / "90-Templates",
            self.vault_root / "99-Dashboard",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        config_path = self.vault_root / ".researchos" / "config.yaml"
        if not config_path.exists():
            atomic_write_text(
                config_path,
                "# ResearchOS Vault Configuration\nschema_version: 1\ncreated_at: "
                + utc_now().isoformat()
                + "\n",
            )

        # Copy templates from repository templates dir if available
        repo_templates = Path(__file__).resolve().parent.parent.parent.parent / "templates"
        vault_templates = self.vault_root / "90-Templates"
        if repo_templates.exists():
            for tpl in repo_templates.glob("*.md"):
                dest = vault_templates / tpl.name
                if not dest.exists():
                    shutil.copy2(tpl, dest)

        # Write or touch initial dashboards
        self.generate_dashboards()

        return {"status": "success", "vault_root": str(self.vault_root)}

    def create_project(
        self,
        name: str,
        research_question: str | None = None,
        objectives: list[str] | None = None,
        scope: str | None = None,
        members: list[str] | None = None,
        repositories: list[str] | None = None,
    ) -> Project:
        """Creates a new Project entity and directory structure."""
        if not name or not name.strip():
            raise ValidationError("Project name cannot be empty.")

        project_id = self.id_gen.generate_id(IdPrefix.PROJECT)
        project = Project(
            id=project_id,
            name=name.strip(),
            status=ProjectStatus.ACTIVE,
            research_question=research_question,
            objectives=objectives or [],
            scope=scope,
            members=members or [],
            repositories=repositories or [],
        )

        proj_dir = self.store.get_project_dir(project_id)
        for subdir in ["Experiments", "Runs", "Findings", "Claims", "Decisions", "Artifacts"]:
            (proj_dir / subdir).mkdir(parents=True, exist_ok=True)

        # Load template for project
        tpl_path = self.vault_root / "90-Templates" / "project.md"
        body = tpl_path.read_text(encoding="utf-8") if tpl_path.exists() else "# {name}\n\n## Research Background\n\n## Research Questions\n"
        body = body.replace("{name}", project.name).replace("{id}", project.id)

        # Save PROJECT.md
        self.store.save_entity(project, body, path=proj_dir / "PROJECT.md")

        # Create STATUS.md
        status_md = f"# Status: {project.name}\n\n**Project ID**: {project.id}\n**Status**: {project.status.value}\n**Last Updated**: {project.updated_at.isoformat()}\n\n## Overview\nProject initialized.\n\n## Metrics\n- Experiments: 0\n- Runs: 0\n- Literature: 0\n- Claims: 0\n"
        atomic_write_text(proj_dir / "STATUS.md", status_md)

        # Create HANDOFF.md
        handoff_md = f"# Handoff: {project.name}\n\n**Current Focus**: Project kickoff and experimental planning.\n**Modified Files**:\n- `PROJECT.md`\n- `STATUS.md`\n\n## Open Issues\nNone.\n\n## Next Steps\n1. Formulate initial research questions and hypotheses.\n2. Review related literature in `01-Literature`.\n3. Create first experiment plan in `Experiments/`.\n"
        atomic_write_text(proj_dir / "HANDOFF.md", handoff_md)

        # Create CHANGELOG.md
        changelog_md = f"# Changelog: {project.name}\n\n- **{utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}**: Project {project.id} created.\n"
        atomic_write_text(proj_dir / "CHANGELOG.md", changelog_md)

        self.generate_dashboards()
        return project

    def get_project(self, project_id: str) -> tuple[Project, str]:
        path = self.store.resolve_entity_path(project_id)
        if not path.exists():
            raise EntityNotFoundError(f"Project {project_id} not found at {path}.")
        return self.store.load_entity(path, Project)

    def list_projects(self) -> list[Project]:
        projects_dir = self.vault_root / "00-Projects"
        if not projects_dir.exists():
            return []

        results: list[Project] = []
        for p in sorted(projects_dir.iterdir()):
            proj_md = p / "PROJECT.md"
            if proj_md.is_file():
                try:
                    proj, _ = self.store.load_entity(proj_md, Project)
                    results.append(proj)
                except Exception:
                    continue
        return results

    def get_project_status(self, project_id: str) -> dict[str, Any]:
        proj, _ = self.get_project(project_id)
        proj_dir = self.store.get_project_dir(project_id)

        exp_count = len(list((proj_dir / "Experiments").glob("*.md")))
        run_count = len(list((proj_dir / "Runs").glob("*.md")))
        finding_count = len(list((proj_dir / "Findings").glob("*.md")))
        claim_count = len(list((proj_dir / "Claims").glob("*.md")))

        status_file = proj_dir / "STATUS.md"
        handoff_file = proj_dir / "HANDOFF.md"

        return {
            "project_id": proj.id,
            "name": proj.name,
            "status": proj.status.value,
            "experiments_count": exp_count,
            "runs_count": run_count,
            "findings_count": finding_count,
            "claims_count": claim_count,
            "status_file": str(status_file) if status_file.exists() else None,
            "handoff_file": str(handoff_file) if handoff_file.exists() else None,
            "updated_at": proj.updated_at.isoformat(),
        }

    def generate_dashboards(self) -> None:
        """Regenerates standard markdown dashboards in 99-Dashboard/."""
        dash_dir = self.vault_root / "99-Dashboard"
        dash_dir.mkdir(parents=True, exist_ok=True)

        # 1. Projects.md
        projects = self.list_projects()
        p_lines = [
            "# Projects Overview",
            f"*Generated: {utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}*",
            "",
            "| Project ID | Name | Status | Question | Updated |",
            "|---|---|---|---|---|",
        ]
        for p in projects:
            link = f"[{p.id}](../00-Projects/{p.id}/PROJECT.md)"
            q = (p.research_question or "-").replace("|", "\\|")
            p_lines.append(f"| {link} | {p.name} | `{p.status.value}` | {q} | {p.updated_at.strftime('%Y-%m-%d')} |")
        atomic_write_text(dash_dir / "Projects.md", "\n".join(p_lines) + "\n")

        # 2. Pending-Experiments.md
        pending_lines = [
            "# Pending Experiments",
            f"*Generated: {utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}*",
            "",
            "| Experiment ID | Project | Title | Status | Outcome |",
            "|---|---|---|---|---|",
        ]
        for p in projects:
            exp_dir = self.store.get_project_dir(p.id) / "Experiments"
            if exp_dir.exists():
                for exp_file in sorted(exp_dir.glob("*.md")):
                    try:
                        exp, _ = self.store.load_entity(exp_file, Experiment)
                        if exp.status not in (ExperimentStatus.COMPLETED, ExperimentStatus.ABANDONED):
                            link = f"[{exp.id}](../00-Projects/{p.id}/Experiments/{exp.id}.md)"
                            pending_lines.append(
                                f"| {link} | {p.name} | {exp.title} | `{exp.status.value}` | `{exp.outcome.value}` |"
                            )
                    except Exception:
                        continue
        atomic_write_text(dash_dir / "Pending-Experiments.md", "\n".join(pending_lines) + "\n")

        # 3. Literature-Overview.md
        lit_dir = self.vault_root / "01-Literature"
        lit_lines = [
            "# Literature Overview",
            f"*Generated: {utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}*",
            "",
            "| Paper ID | Citekey | Title | Year | Reading Status |",
            "|---|---|---|---|---|",
        ]
        if lit_dir.exists():
            for paper_file in sorted(lit_dir.glob("*.md")):
                try:
                    paper, _ = self.store.load_entity(paper_file, Paper)
                    link = f"[{paper.id}](../01-Literature/{paper.id}.md)"
                    lit_lines.append(
                        f"| {link} | `{paper.citekey}` | {paper.title} | {paper.year or '-'} | `{paper.reading_status.value}` |"
                    )
                except Exception:
                    continue
        atomic_write_text(dash_dir / "Literature-Overview.md", "\n".join(lit_lines) + "\n")
