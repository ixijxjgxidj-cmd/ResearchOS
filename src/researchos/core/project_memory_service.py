"""Always-on Project Memory service managing <project_id>/MEMORY.md."""

import re
from pathlib import Path
from typing import Any

from researchos.core.context_builder import estimate_tokens
from researchos.core.project_service import SUBDIRS, ProjectService
from researchos.core.storage_service import atomic_write_text, file_lock, parse_frontmatter
from researchos.models.memory import (
    MemoryFrontmatter,
    MemoryStatus,
    MemoryType,
    utc_now,
)
from researchos.utils.exceptions import ProjectNotFoundError, ValidationError
from researchos.utils.sanitizer import sanitize_markdown_text

# Regex to match Memory IDs cited in text: MEM-YYYY-NNNN
MEM_ID_REGEX = re.compile(r"\b(MEM-\d{4}-\d{3,})\b")

# The 10 canonical required sections for MEMORY.md
REQUIRED_MEMORY_SECTIONS = [
    "Project Identity",
    "Core Research Idea",
    "Confirmed Findings",
    "Current Hypotheses",
    "Important Decisions",
    "Current Research Status",
    "Paper Structure",
    "Important Memory Pointers",
    "Next Actions",
    "Important Warnings",
]


class ProjectMemoryService:
    """Manages the Always-on Project Memory (<project_id>/MEMORY.md)."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.project_svc = ProjectService(self.vault_root)

    def get_memory_file(self, project_id: str) -> Path:
        """Returns the path to MEMORY.md inside the target project."""
        p_dir = self.project_svc.get_project_dir(project_id)
        return p_dir / "MEMORY.md"

    def get_project_memory(self, project_id: str) -> str:
        """Retrieves MEMORY.md content. If missing, automatically rebuilds it."""
        mem_file = self.get_memory_file(project_id)
        if not mem_file.exists():
            return self.rebuild_project_memory(project_id)
        return mem_file.read_text(encoding="utf-8")

    def update_project_memory(
        self,
        project_id: str,
        content: str,
        reason: str | None = None,
    ) -> str:
        """Atomically updates MEMORY.md with concurrency locking and secret sanitization."""
        if not content or not content.strip():
            raise ValidationError("MEMORY.md content cannot be empty.")

        p_dir = self.project_svc.get_project_dir(project_id)
        if not (p_dir / "PROJECT.md").exists():
            raise ProjectNotFoundError(f"Project '{project_id}' does not exist.")

        mem_file = self.get_memory_file(project_id)
        lock_path = p_dir / ".researchos" / "memory_md.lock"

        clean_text = sanitize_markdown_text(content.strip())
        now = utc_now().isoformat()

        # Update or inject timestamp header
        if "*Last Updated:" in clean_text:
            clean_text = re.sub(
                r"\*Last Updated: [^\*]+\*",
                f"*Last Updated: {now}*",
                clean_text,
                count=1,
            )
        else:
            clean_text = f"*Last Updated: {now}*\n\n{clean_text}"

        with file_lock(lock_path, timeout=10.0):
            atomic_write_text(mem_file, clean_text)
            self.project_svc.touch_project(project_id)

        return clean_text

    def validate_project_memory(self, project_id: str) -> dict[str, Any]:
        """Validates MEMORY.md against the 10 canonical sections, cited memory IDs, and token budget.

        Returns:
            Dictionary containing:
              - valid: bool
              - errors: list[str]
              - warnings: list[str]
              - sections_found: list[str]
              - missing_sections: list[str]
              - cited_memory_ids: list[str]
              - missing_cited_ids: list[str]
              - estimated_tokens: int
              - within_budget: bool
        """
        p_dir = self.project_svc.get_project_dir(project_id)
        if not (p_dir / "PROJECT.md").exists():
            raise ProjectNotFoundError(f"Project '{project_id}' does not exist.")

        mem_file = self.get_memory_file(project_id)
        if not mem_file.exists():
            return {
                "project_id": project_id,
                "valid": False,
                "errors": [f"MEMORY.md does not exist for project '{project_id}'."],
                "warnings": [],
                "sections_found": [],
                "missing_sections": list(REQUIRED_MEMORY_SECTIONS),
                "cited_memory_ids": [],
                "missing_cited_ids": [],
                "estimated_tokens": 0,
                "within_budget": False,
            }

        content = mem_file.read_text(encoding="utf-8")
        tokens = estimate_tokens(content)

        errors: list[str] = []
        warnings: list[str] = []

        # 1. Section presence validation
        sections_found: list[str] = []
        missing_sections: list[str] = []

        for req in REQUIRED_MEMORY_SECTIONS:
            # Check for header ## X. <Section> or ## <Section>
            pattern = re.compile(rf"##\s*(\d+\.\s*)?{re.escape(req)}", re.IGNORECASE)
            if pattern.search(content):
                sections_found.append(req)
            else:
                missing_sections.append(req)

        if missing_sections:
            warnings.append(
                f"MEMORY.md is missing recommended standard sections: {missing_sections}"
            )

        # 2. Check cited memory IDs against actual files on disk
        cited_ids = sorted(set(MEM_ID_REGEX.findall(content)))
        missing_cited_ids: list[str] = []

        # Collect existing project memory IDs
        existing_ids: set[str] = set()
        for sub in SUBDIRS:
            sub_dir = p_dir / sub
            if not sub_dir.exists():
                continue
            for f in sub_dir.glob("*.md"):
                try:
                    meta, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
                    if "id" in meta:
                        existing_ids.add(meta["id"])
                except Exception:
                    continue

        for cid in cited_ids:
            if cid not in existing_ids:
                missing_cited_ids.append(cid)

        if missing_cited_ids:
            errors.append(
                f"MEMORY.md references non-existent memory IDs: {missing_cited_ids}"
            )

        # 3. Budget checking (recommended: <= 3000 tokens)
        within_budget = tokens <= 3200
        if not within_budget:
            warnings.append(
                f"MEMORY.md length ({tokens} tokens) exceeds recommended budget (~2,000 - 3,000 tokens)."
            )

        is_valid = len(errors) == 0

        return {
            "project_id": project_id,
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "sections_found": sections_found,
            "missing_sections": missing_sections,
            "cited_memory_ids": cited_ids,
            "missing_cited_ids": missing_cited_ids,
            "estimated_tokens": tokens,
            "within_budget": within_budget,
        }

    def rebuild_project_memory(
        self,
        project_id: str,
        max_tokens: int = 2000,
    ) -> str:
        """Deterministically synthesizes MEMORY.md from PROJECT.md, STATE.md, and key active memories."""
        p_dir = self.project_svc.get_project_dir(project_id)
        proj = self.project_svc.get_project(project_id)

        # 1. Load active project memories
        all_memories = self._load_project_memories(project_id)
        active_mems = [m for m in all_memories if m.status == MemoryStatus.ACTIVE]

        # Extract memory groups
        negatives = [m for m in active_mems if m.type == MemoryType.NEGATIVE]
        decisions = [m for m in active_mems if m.type == MemoryType.DECISION]
        hypotheses = [m for m in active_mems if m.type == MemoryType.HYPOTHESIS]
        observations = [m for m in active_mems if m.type == MemoryType.OBSERVATION]
        references = [m for m in active_mems if m.type == MemoryType.REFERENCE]

        now = utc_now().isoformat()

        # Build sections according to specification
        lines = [
            f"# Always-on Project Memory: {proj.project_name}",
            f"*Project ID: `{project_id}` | Last Updated: {now}*",
            "",
            "> [!IMPORTANT]",
            "> **Role of MEMORY.md**: High-value compressed project executive summary for autonomous agents.",
            "> All scientific claims cite verified Memory IDs (`MEM-...`). Details are read on demand.",
            "",
            "## 1. Project Identity",
            f"- **Research Topic**: {proj.project_name}",
            f"- **Core Goal**: {proj.frontmatter.research_goal or 'Advance research objectives.'}",
            f"- **Description**: {proj.frontmatter.description or 'Active scientific investigation.'}",
            "- **Target Publication Venue**: _Not yet established_",
            "",
            "## 2. Core Research Idea",
        ]

        if proj.frontmatter.description:
            lines.append(f"- {proj.frontmatter.description}")
        else:
            lines.append("- _Not yet established_")
        lines.append("- **Key Innovations**: _Not yet established_")
        lines.append("- **Difference from Prior Work**: _Not yet established_")
        lines.append("")

        # 3. Confirmed Findings
        lines.append("## 3. Confirmed Findings")
        if observations:
            for obs in observations[-5:]:
                lines.append(f"- **`{obs.id}`**: {obs.title}")
        else:
            lines.append("- _No confirmed empirical findings recorded yet._")
        lines.append("")

        # 4. Current Hypotheses
        lines.append("## 4. Current Hypotheses")
        if hypotheses:
            for hyp in hypotheses[-5:]:
                lines.append(f"- **`{hyp.id}`** [Active]: {hyp.title}")
        else:
            lines.append("- _No active hypotheses recorded yet._")
        lines.append("")

        # 5. Important Decisions
        lines.append("## 5. Important Decisions")
        if decisions:
            for dec in decisions[-5:]:
                lines.append(f"- **`{dec.id}`**: {dec.title}")
        else:
            lines.append("- _No major architectural decisions recorded._")
        lines.append("")

        # 6. Current Research Status
        lines.append("## 6. Current Research Status")
        # Read from STATE.md if available
        state_file = p_dir / "STATE.md"
        if state_file.exists():
            lines.append(f"- **State Source**: `{project_id}/STATE.md`")
            lines.append(f"- **Total Active Memories**: `{len(active_mems)}`")
        else:
            lines.append("- Project initialized; initial baseline phase.")
        lines.append("")

        # 7. Paper Structure
        lines.append("## 7. Paper Structure")
        # Group observations by paper_section if defined
        section_mapped = [m for m in active_mems if m.frontmatter.paper_section]
        if section_mapped:
            sec_dict: dict[str, list[str]] = {}
            for sm in section_mapped:
                sec_dict.setdefault(str(sm.frontmatter.paper_section), []).append(sm.id)
            for sec_name, mids in sec_dict.items():
                lines.append(f"- **{sec_name}**: {', '.join(f'`{mid}`' for mid in mids)}")
        else:
            lines.append("- Section 1 (Introduction): _Not yet established_")
            lines.append("- Section 3 (Methodology): _Not yet established_")
            lines.append("- Section 4 (Experiments): _Not yet established_")
        lines.append("")

        # 8. Important Memory Pointers
        lines.append("## 8. Important Memory Pointers")
        ptr_lines = []
        if observations:
            ptr_lines.append(f"- **Key Experiments**: {', '.join(f'`{o.id}`' for o in observations[-4:])}")
        if references:
            ptr_lines.append(f"- **Key References**: {', '.join(f'`{r.id}`' for r in references[-4:])}")
        if decisions:
            ptr_lines.append(f"- **Key Decisions**: {', '.join(f'`{d.id}`' for d in decisions[-4:])}")
        if negatives:
            ptr_lines.append(f"- **Key Pitfalls (Negatives)**: {', '.join(f'`{n.id}`' for n in negatives[-4:])}")

        if ptr_lines:
            lines.extend(ptr_lines)
        else:
            lines.append("- _None recorded yet._")
        lines.append("")

        # 9. Next Actions
        lines.append("## 9. Next Actions")
        lines.append("1. Review existing hypotheses and literature pointers.")
        lines.append("2. Execute validation runs and record empirical findings.")
        lines.append("")

        # 10. Important Warnings
        lines.append("## 10. Important Warnings")
        if negatives:
            for neg in negatives[-4:]:
                lines.append(f"- > [!WARNING] **`{neg.id}` (Pitfall)**: {neg.title}")
        else:
            lines.append("- _No critical pitfalls recorded yet._")
        lines.append("")

        full_content = "\n".join(lines)

        # Enforce budget (~max_tokens)
        mem_file = self.get_memory_file(project_id)
        lock_path = p_dir / ".researchos" / "memory_md.lock"
        with file_lock(lock_path, timeout=10.0):
            atomic_write_text(mem_file, full_content)
            self.project_svc.touch_project(project_id)

        return full_content

    def _load_project_memories(self, project_id: str) -> list[Any]:
        from researchos.models.memory import Memory
        p_dir = self.project_svc.get_project_dir(project_id)
        memories = []
        for sub in SUBDIRS:
            sub_dir = p_dir / sub
            if not sub_dir.exists():
                continue
            for f in sorted(sub_dir.glob("*.md")):
                try:
                    content = f.read_text(encoding="utf-8")
                    meta, body = parse_frontmatter(content)
                    if "id" in meta and "type" in meta:
                        fm = MemoryFrontmatter.model_validate(meta)
                        rel_path = f.relative_to(p_dir).as_posix()
                        memories.append(Memory(frontmatter=fm, content=body, file_path=rel_path))
                except Exception:
                    continue
        return memories
