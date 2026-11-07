"""Handoff management service for seamless multi-agent shift changes."""

from pathlib import Path
from typing import Any

from researchos.core.exceptions import EntityNotFoundError
from researchos.core.models import Project, utc_now
from researchos.storage.atomic_writer import atomic_write_text
from researchos.storage.markdown_store import MarkdownStore


class HandoffService:
    """Updates HANDOFF.md and STATUS.md for inter-agent context continuity."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.store = MarkdownStore(self.vault_root)

    def update_handoff(
        self,
        project_id: str,
        current_focus: str,
        completed_since_last: list[str] | None = None,
        modified_files: list[str] | None = None,
        open_issues: list[str] | None = None,
        next_steps: list[str] | None = None,
        target_files_for_next_agent: list[str] | None = None,
    ) -> str:
        proj_path = self.store.resolve_entity_path(project_id)
        if not proj_path.exists():
            raise EntityNotFoundError(f"Project {project_id} not found.")

        proj, _ = self.store.load_entity(proj_path, Project)
        proj_dir = self.store.get_project_dir(project_id)

        now_str = utc_now().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Construct HANDOFF.md
        lines: list[str] = [
            f"# Handoff: {proj.name}",
            f"*Last Updated: {now_str}*",
            "",
            f"**Current Focus**: {current_focus}",
            "",
            "## Completed Work Since Last Handoff",
        ]
        if completed_since_last:
            for item in completed_since_last:
                lines.append(f"- {item}")
        else:
            lines.append("- _None recorded._")
        lines.append("")

        lines.append("## Modified Files")
        if modified_files:
            for f in modified_files:
                lines.append(f"- `{f}`")
        else:
            lines.append("- _None specified._")
        lines.append("")

        lines.append("## Open Issues & Blockers")
        if open_issues:
            for issue in open_issues:
                lines.append(f"- {issue}")
        else:
            lines.append("- _No active blockers._")
        lines.append("")

        lines.append("## Next Steps")
        if next_steps:
            for idx, step in enumerate(next_steps, 1):
                lines.append(f"{idx}. {step}")
        else:
            lines.append("1. Continue experimental roadmap.")
        lines.append("")

        lines.append("## Recommended Reading for Next Agent")
        if target_files_for_next_agent:
            for tf in target_files_for_next_agent:
                lines.append(f"- `{tf}`")
        else:
            lines.append(f"- `00-Projects/{project_id}/STATUS.md`")
            lines.append(f"- `00-Projects/{project_id}/PROJECT.md`")
        lines.append("")

        handoff_content = "\n".join(lines)
        atomic_write_text(proj_dir / "HANDOFF.md", handoff_content)

        # Update STATUS.md
        exp_count = len(list((proj_dir / "Experiments").glob("*.md")))
        run_count = len(list((proj_dir / "Runs").glob("*.md")))
        finding_count = len(list((proj_dir / "Findings").glob("*.md")))
        claim_count = len(list((proj_dir / "Claims").glob("*.md")))

        status_content = (
            f"# Status: {proj.name}\n\n"
            f"**Project ID**: `{proj.id}`\n"
            f"**Current Status**: `{proj.status.value}`\n"
            f"**Last Handoff**: {now_str}\n\n"
            f"## Active Focus\n{current_focus}\n\n"
            f"## Metrics\n"
            f"- Experiments: {exp_count}\n"
            f"- Runs: {run_count}\n"
            f"- Findings: {finding_count}\n"
            f"- Claims: {claim_count}\n"
        )
        atomic_write_text(proj_dir / "STATUS.md", status_content)

        # Update CHANGELOG.md
        changelog_file = proj_dir / "CHANGELOG.md"
        if changelog_file.exists():
            entry = f"- **{now_str}**: Handoff updated: {current_focus[:80]}...\n"
            with open(changelog_file, "a", encoding="utf-8") as f:
                f.write(entry)

        return handoff_content
