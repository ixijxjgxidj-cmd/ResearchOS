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
        """Resolves and validates the project directory (enforces case-normalized lowercase IDs)."""
        if not project_id or not project_id.strip():
            raise ValidationError("project_id cannot be empty.")
        clean_id = project_id.strip().lower()
        p_dir = validate_path_within(self.vault_root, clean_id)
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
        raw_pid = project_id.strip() if project_id and project_id.strip() else slugify_project_id(clean_name)
        pid = raw_pid.lower()
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

            # 6. MEMORY.md (Always-on Project Memory initialization)
            mem_file = p_dir / "MEMORY.md"
            if not mem_file.exists():
                from researchos.core.project_memory_service import ProjectMemoryService
                pms = ProjectMemoryService(self.vault_root)
                pms.rebuild_project_memory(pid)

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

    def validate_project(self, project_id: str, strict: bool = True) -> dict[str, Any]:
        """Validates all memory files, frontmatters, links, relations, and folder integrity.

        Args:
            project_id: Unique project identifier.
            strict: If True, broken links and invalid relation references cause valid=False.
                    If False, broken links and invalid relations are treated as warnings.

        Returns:
            Dictionary containing validation results and detailed diagnostic lists:
              - valid: bool
              - errors: list[str] (parse/schema failures, duplicate IDs)
              - warnings: list[str]
              - broken_links: list[dict] (source file, line number, target, message)
              - orphan_memories: list[str] (memories not indexed in INDEX.md)
              - duplicate_ids: list[str] (conflicting memory IDs)
              - invalid_relations: list[dict] (broken related/supersedes pointers)
              - checked_files: int
              - total_memories: int
        """
        p_dir = self.get_project_dir(project_id)
        self.get_project(project_id)

        errors: list[str] = []
        warnings: list[str] = []
        broken_links: list[dict[str, Any]] = []
        invalid_relations: list[dict[str, Any]] = []
        duplicate_ids_map: dict[str, list[str]] = {}
        all_discovered_ids: dict[str, MemoryFrontmatter] = {}
        valid_memories = 0
        checked_files = 0

        # Scan root control files
        for root_file in ("PROJECT.md", "STATE.md", "INDEX.md", "HANDOFF.md", "MEMORY.md"):
            rf = p_dir / root_file
            if rf.exists():
                checked_files += 1
                try:
                    rf_content = rf.read_text(encoding="utf-8")
                    bl_list = LinkingService.verify_internal_links_detailed(p_dir, rf, rf_content)
                    broken_links.extend(bl_list)
                except Exception as exc:
                    warnings.append(f"Failed to read root file {root_file}: {exc}")
            else:
                warnings.append(f"Missing recommended root file: {root_file}")

        # Scan all memory subdirectories
        for sub in SUBDIRS:
            folder = p_dir / sub
            if not folder.exists():
                continue
            for f in sorted(folder.glob("*.md")):
                checked_files += 1
                rel_f_path = f.relative_to(p_dir).as_posix()
                try:
                    content = f.read_text(encoding="utf-8")
                    meta, body = parse_frontmatter(content)
                    fm = MemoryFrontmatter.model_validate(meta)
                    valid_memories += 1

                    # Track duplicate IDs
                    duplicate_ids_map.setdefault(fm.id, []).append(rel_f_path)
                    all_discovered_ids[fm.id] = fm

                    # Check internal markdown links
                    bls = LinkingService.verify_internal_links_detailed(p_dir, f, body)
                    broken_links.extend(bls)

                except Exception as exc:
                    errors.append(f"{rel_f_path}: {exc}")

        # Check duplicate IDs
        duplicate_ids: list[str] = [
            f"ID '{mid}' shared by: {', '.join(paths)}"
            for mid, paths in duplicate_ids_map.items()
            if len(paths) > 1
        ]
        if duplicate_ids:
            errors.extend(duplicate_ids)

        # Check relations (related, supersedes, superseded_by)
        for mid, fm in all_discovered_ids.items():
            for rel in fm.related:
                if rel not in all_discovered_ids:
                    invalid_relations.append({
                        "source_id": mid,
                        "relation_type": "related",
                        "target_id": rel,
                        "message": f"Memory '{mid}' references non-existent related memory '{rel}'",
                    })
            if fm.supersedes and fm.supersedes not in all_discovered_ids:
                invalid_relations.append({
                    "source_id": mid,
                    "relation_type": "supersedes",
                    "target_id": fm.supersedes,
                    "message": f"Memory '{mid}' references non-existent supersedes target '{fm.supersedes}'",
                })
            if fm.superseded_by and fm.superseded_by not in all_discovered_ids:
                invalid_relations.append({
                    "source_id": mid,
                    "relation_type": "superseded_by",
                    "target_id": fm.superseded_by,
                    "message": f"Memory '{mid}' references non-existent superseded_by target '{fm.superseded_by}'",
                })

        # Check orphan memories (memories missing from INDEX.md)
        orphan_memories: list[str] = []
        index_file = p_dir / "INDEX.md"
        if index_file.exists():
            index_text = index_file.read_text(encoding="utf-8")
            for mid in all_discovered_ids:
                if mid not in index_text:
                    orphan_memories.append(mid)
        if orphan_memories:
            warnings.append(
                f"{len(orphan_memories)} memories are not indexed in INDEX.md (run index_rebuild to fix)"
            )

        # Determine validity:
        # Errors (schema/duplicate IDs) always invalidate.
        # In strict mode, broken links or invalid relations also invalidate.
        is_valid = len(errors) == 0
        if strict:
            if len(broken_links) > 0 or len(invalid_relations) > 0:
                is_valid = False

        return {
            "project_id": project_id,
            "valid": is_valid,
            "strict": strict,
            "total_memories": valid_memories,
            "checked_files": checked_files,
            "errors": errors,
            "warnings": warnings,
            "broken_links": broken_links,
            "orphan_memories": orphan_memories,
            "duplicate_ids": duplicate_ids,
            "invalid_relations": invalid_relations,
        }
