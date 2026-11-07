"""Project lifecycle service managing independent project folders, state, and index."""

from pathlib import Path
from typing import Any

from researchos.core.linking_service import LinkingService
from researchos.core.storage_service import (
    atomic_write_text,
    dump_frontmatter,
    file_lock,
    parse_frontmatter,
    validate_path_within,
)
from researchos.models.memory import (
    MemoryFrontmatter,
    MemoryStatus,
    MemoryType,
    Project,
    ProjectFrontmatter,
    utc_now,
)
from researchos.utils.exceptions import (
    ProjectNotFoundError,
    ValidationError,
)
from researchos.utils.ids import slugify_project_id

TYPE_TO_DIR = {
    MemoryType.KNOWLEDGE: "knowledge",
    MemoryType.DECISION: "decisions",
    MemoryType.HYPOTHESIS: "hypotheses",
    MemoryType.OBSERVATION: "observations",
    MemoryType.NEGATIVE: "negative",
    MemoryType.REFERENCE: "references",
    MemoryType.HANDOFF: "handoffs",
}

SUBDIRS = [
    "knowledge",
    "decisions",
    "hypotheses",
    "observations",
    "negative",
    "references",
    "handoffs",
    "archive",
]


class ProjectService:
    """Manages independent, isolated research project folders in the ResearchVault."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.vault_root.mkdir(parents=True, exist_ok=True)

    def get_project_dir(self, project_id: str) -> Path:
        """Resolves and validates the project directory."""
        if not project_id or not project_id.strip():
            raise ValidationError("project_id cannot be empty.")
        p_dir = validate_path_within(self.vault_root, project_id.strip())
        return p_dir

    def create_project(
        self,
        name: str,
        project_id: str | None = None,
        description: str | None = None,
        research_goal: str | None = None,
        tags: list[str] | None = None,
    ) -> Project:
        """Idempotently creates a new independent project folder with standard structure."""
        if not name or not name.strip():
            raise ValidationError("Project name cannot be empty.")

        clean_name = name.strip()
        pid = project_id.strip() if project_id and project_id.strip() else slugify_project_id(clean_name)
        p_dir = self.get_project_dir(pid)

        # 1. Create subdirectories
        for sub in SUBDIRS:
            (p_dir / sub).mkdir(parents=True, exist_ok=True)
        (p_dir / ".researchos").mkdir(parents=True, exist_ok=True)

        now = utc_now()
        proj_file = p_dir / "PROJECT.md"
        state_file = p_dir / "STATE.md"
        index_file = p_dir / "INDEX.md"
        handoff_file = p_dir / "HANDOFF.md"

        lock_path = p_dir / ".researchos" / "project.lock"
        with file_lock(lock_path, timeout=10.0):
            # 2. PROJECT.md (Idempotent: don't overwrite if exists)
            if not proj_file.exists():
                pfm = ProjectFrontmatter(
                    project_id=pid,
                    project_name=clean_name,
                    description=description or f"Research project: {clean_name}",
                    research_goal=research_goal or "Advance research objectives.",
                    created_at=now,
                    updated_at=now,
                    status="active",
                    tags=tags or [],
                )
                body = (
                    f"# {clean_name}\n\n"
                    f"**Project ID**: `{pid}`\n"
                    f"**Status**: active\n"
                    f"**Goal**: {pfm.research_goal}\n\n"
                    f"## Overview\n\n{pfm.description}\n"
                )
                content = dump_frontmatter(pfm.model_dump(mode="json"), body)
                atomic_write_text(proj_file, content)

            # 3. STATE.md (Idempotent: don't overwrite if exists)
            if not state_file.exists():
                state_body = (
                    f"# Current State: {clean_name}\n\n"
                    f"*Last Updated: {now.isoformat()}*\n\n"
                    "## 1. 当前研究目标 (Current Goal)\n"
                    f"- {research_goal or 'Define research objectives.'}\n\n"
                    "## 2. 当前已知事实 (Known Facts)\n"
                    "- _Initial project setup._\n\n"
                    "## 3. 当前研究进展 (Current Progress)\n"
                    "- Project initialized.\n\n"
                    "## 4. 当前重要问题 (Key Questions)\n"
                    "- _No pending key questions._\n\n"
                    "## 5. 尚未解决的问题 (Unresolved Issues)\n"
                    "- _None recorded._\n\n"
                    "## 6. 最近的重要变化 (Recent Changes)\n"
                    f"- [{now.strftime('%Y-%m-%d')}] Project workspace created.\n\n"
                    "## 7. 下一步关注事项 (Next Focus)\n"
                    "- Formulate initial hypotheses and literature references.\n"
                )
                atomic_write_text(state_file, state_body)

            # 4. HANDOFF.md (Idempotent)
            if not handoff_file.exists():
                handoff_body = (
                    f"# Agent Handoff: {clean_name}\n\n"
                    f"*Last Updated: {now.isoformat()}*\n\n"
                    "**Executing Agent**: `system-init`\n\n"
                    "## Current Task\n"
                    "- Project workspace initialization.\n\n"
                    "## Completed Work\n"
                    "- Initial project folder, subdirectories, and index created.\n\n"
                    "## Next Steps for Incoming Agent\n"
                    "1. Review PROJECT.md and STATE.md.\n"
                    "2. Begin recording observations, decisions, and knowledge.\n"
                )
                atomic_write_text(handoff_file, handoff_body)

            # 5. INDEX.md (rebuild or create)
            if not index_file.exists():
                self._write_initial_index(pid, clean_name)

        return self.get_project(pid)

    def _write_initial_index(self, project_id: str, project_name: str) -> None:
        p_dir = self.get_project_dir(project_id)
        index_file = p_dir / "INDEX.md"
        now = utc_now()
        lines = [
            f"# Memory Index: {project_name}",
            f"*Project ID: `{project_id}` | Last Indexed: {now.isoformat()}*",
            "",
            "## Summary",
            "- Total Memories: `0`",
            "",
            "## Memory Catalog",
            "_No memories recorded yet._",
            "",
            "## Archived Memories",
            "_None._",
        ]
        atomic_write_text(index_file, "\n".join(lines))

    def get_project(self, project_id: str) -> Project:
        """Loads and returns Project metadata and file info."""
        p_dir = self.get_project_dir(project_id)
        proj_file = p_dir / "PROJECT.md"
        if not proj_file.exists():
            raise ProjectNotFoundError(f"Project '{project_id}' does not exist at {p_dir}.")

        content = proj_file.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(content)
        pfm = ProjectFrontmatter.model_validate(meta)
        return Project(frontmatter=pfm, body=body, project_dir=str(p_dir))

    def list_projects(self) -> list[Project]:
        """Lists all valid projects in the vault root."""
        projects = []
        if not self.vault_root.exists():
            return []

        for item in sorted(self.vault_root.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                proj_file = item / "PROJECT.md"
                if proj_file.exists():
                    try:
                        p = self.get_project(item.name)
                        projects.append(p)
                    except Exception:
                        continue
        return projects

    def touch_project(self, project_id: str) -> None:
        """Updates the updated_at timestamp of PROJECT.md."""
        p_dir = self.get_project_dir(project_id)
        proj_file = p_dir / "PROJECT.md"
        if not proj_file.exists():
            return

        lock_path = p_dir / ".researchos" / "project.lock"
        with file_lock(lock_path, timeout=5.0):
            content = proj_file.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(content)
            meta["updated_at"] = utc_now().isoformat()
            new_content = dump_frontmatter(meta, body)
            atomic_write_text(proj_file, new_content)

    def rebuild_index(self, project_id: str) -> dict[str, Any]:
        """Scans the project directory and fully regenerates INDEX.md from disk."""
        p_dir = self.get_project_dir(project_id)
        proj = self.get_project(project_id)

        index_file = p_dir / "INDEX.md"
        lock_path = p_dir / ".researchos" / "index.lock"

        with file_lock(lock_path, timeout=10.0):
            # Scan all .md files in the project
            memories: list[tuple[MemoryFrontmatter, Path]] = []
            archived_memories: list[tuple[MemoryFrontmatter, Path]] = []

            for sub in SUBDIRS:
                folder = p_dir / sub
                if not folder.exists():
                    continue
                for f in sorted(folder.glob("*.md")):
                    try:
                        content = f.read_text(encoding="utf-8")
                        meta, _ = parse_frontmatter(content)
                        if "id" in meta and "type" in meta:
                            fm = MemoryFrontmatter.model_validate(meta)
                            if sub == "archive" or fm.status == MemoryStatus.ARCHIVED:
                                archived_memories.append((fm, f))
                            else:
                                memories.append((fm, f))
                    except Exception:
                        continue

            now = utc_now()
            type_counts: dict[str, int] = {}
            for fm, _ in memories:
                t = fm.type.value
                type_counts[t] = type_counts.get(t, 0) + 1

            lines = [
                f"# Memory Index: {proj.project_name}",
                f"*Project ID: `{project_id}` | Last Indexed: {now.isoformat()}*",
                "",
                "## Summary",
                f"- **Active Memories**: `{len(memories)}`",
                f"- **Archived Memories**: `{len(archived_memories)}`",
                "",
                "### Counts by Type",
            ]
            for t_val in MemoryType:
                cnt = type_counts.get(t_val.value, 0)
                lines.append(f"- **{t_val.value}**: {cnt}")
            lines.append("")

            # Group active memories by type
            lines.append("## Memory Catalog")
            for t_val in MemoryType:
                group = [m for m in memories if m[0].type == t_val]
                if not group:
                    continue
                lines.append(f"### {t_val.value.capitalize()} ({len(group)})")
                lines.append("")
                lines.append("| ID | Title | Status | Tags | Source | Supersedes |")
                lines.append("|---|---|---|---|---|---|")
                for fm, path in group:
                    rel_link = LinkingService.compute_relative_link(index_file, path)
                    title_link = f"[{fm.title}]({rel_link})"
                    tag_str = ", ".join(fm.tags) if fm.tags else "-"
                    src = fm.source_ref or fm.source_agent or "-"
                    sup = fm.supersedes or "-"
                    lines.append(
                        f"| `{fm.id}` | {title_link} | `{fm.status.value}` | {tag_str} | {src} | {sup} |"
                    )
                lines.append("")

            # Archived Section
            lines.append("## Archived Memories")
            if archived_memories:
                lines.append("| ID | Title | Original Type | Path |")
                lines.append("|---|---|---|---|")
                for fm, path in archived_memories:
                    rel_link = LinkingService.compute_relative_link(index_file, path)
                    title_link = f"[{fm.title}]({rel_link})"
                    lines.append(f"| `{fm.id}` | {title_link} | `{fm.type.value}` | `{rel_link}` |")
            else:
                lines.append("_No archived memories._")

            lines.append("")
            index_content = "\n".join(lines)
            atomic_write_text(index_file, index_content)

        return {
            "project_id": project_id,
            "active_memories": len(memories),
            "archived_memories": len(archived_memories),
            "type_counts": type_counts,
            "status": "success",
        }

    def validate_project(self, project_id: str) -> dict[str, Any]:
        """Validates all memory files, frontmatters, and links in the project."""
        p_dir = self.get_project_dir(project_id)
        self.get_project(project_id)

        valid_memories = 0
        errors: list[str] = []
        broken_links: list[str] = []

        for sub in SUBDIRS:
            folder = p_dir / sub
            if not folder.exists():
                continue
            for f in sorted(folder.glob("*.md")):
                try:
                    content = f.read_text(encoding="utf-8")
                    meta, body = parse_frontmatter(content)
                    MemoryFrontmatter.model_validate(meta)
                    valid_memories += 1
                    # check internal links
                    links_broken = LinkingService.verify_internal_links(p_dir, f, body)
                    for bl in links_broken:
                        broken_links.append(f"{f.name}: {bl}")
                except Exception as exc:
                    errors.append(f"{f.relative_to(p_dir)}: {exc}")

        return {
            "project_id": project_id,
            "valid": len(errors) == 0,
            "total_memories": valid_memories,
            "errors": errors,
            "broken_links": broken_links,
        }
