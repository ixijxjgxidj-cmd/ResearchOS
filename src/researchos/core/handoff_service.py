"""Agent handoff management service for inter-agent context persistence."""

from pathlib import Path

from researchos.core.memory_service import MemoryService
from researchos.core.project_service import ProjectService
from researchos.core.storage_service import atomic_write_text, file_lock
from researchos.models.memory import Memory, MemoryType, utc_now
from researchos.utils.exceptions import ProjectNotFoundError


class HandoffService:
    """Manages agent shift handoffs and state synchronization."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.project_svc = ProjectService(self.vault_root)
        self.memory_svc = MemoryService(self.vault_root)

    def create_handoff(
        self,
        project_id: str,
        task: str,
        completed_work: list[str] | None = None,
        current_progress: str | None = None,
        important_findings: list[str] | None = None,
        decisions_made: list[str] | None = None,
        issues_encountered: list[str] | None = None,
        unresolved_items: list[str] | None = None,
        next_steps: list[str] | None = None,
        related_memory_ids: list[str] | None = None,
        related_files: list[str] | None = None,
        agent_id: str | None = None,
    ) -> Memory:
        """Records an agent handoff, archives it in handoffs/, and updates HANDOFF.md and STATE.md."""
        p_dir = self.project_svc.get_project_dir(project_id)
        if not (p_dir / "PROJECT.md").exists():
            raise ProjectNotFoundError(f"Project '{project_id}' does not exist.")

        agent = agent_id or "agent"
        now = utc_now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")

        # 1. Format handoff markdown body
        lines = [
            f"# Handoff: {task.strip()}",
            f"*Timestamp: {now_str} | Executing Agent: `{agent}`*",
            "",
            "## Current Task",
            f"{task.strip()}",
            "",
            "## Completed Work",
        ]
        if completed_work:
            for item in completed_work:
                lines.append(f"- {item}")
        else:
            lines.append("- _None recorded._")
        lines.append("")

        lines.append("## Current Progress & Findings")
        if current_progress:
            lines.append(f"**Progress**: {current_progress}\n")
        if important_findings:
            lines.append("**Key Findings**:")
            for find in important_findings:
                lines.append(f"- {find}")
        else:
            lines.append("- _No specific findings noted._")
        lines.append("")

        lines.append("## Decisions Made")
        if decisions_made:
            for dec in decisions_made:
                lines.append(f"- {dec}")
        else:
            lines.append("- _No major decisions recorded._")
        lines.append("")

        lines.append("## Issues & Unresolved Items")
        if issues_encountered:
            lines.append("**Issues Encountered**:")
            for issue in issues_encountered:
                lines.append(f"- {issue}")
        if unresolved_items:
            lines.append("**Unresolved Items**:")
            for unres in unresolved_items:
                lines.append(f"- {unres}")
        if not issues_encountered and not unresolved_items:
            lines.append("- _None._")
        lines.append("")

        lines.append("## Next Steps for Incoming Agent")
        if next_steps:
            for idx, step in enumerate(next_steps, 1):
                lines.append(f"{idx}. {step}")
        else:
            lines.append("1. Continue research according to project goals.")
        lines.append("")

        lines.append("## Related References & Files")
        if related_memory_ids:
            lines.append(f"- **Memories**: {', '.join(f'`{mid}`' for mid in related_memory_ids)}")
        if related_files:
            lines.append(f"- **Files**: {', '.join(f'`{f}`' for f in related_files)}")
        if not related_memory_ids and not related_files:
            lines.append("- _None cited._")

        body_content = "\n".join(lines)

        # 2. Add as permanent memory record in handoffs/
        mem = self.memory_svc.add_memory(
            project_id=project_id,
            type=MemoryType.HANDOFF,
            title=f"Handoff: {task.strip()[:60]}",
            content=body_content,
            tags=["handoff", agent],
            source_agent=agent,
            source_skill="memory-handoff",
            related_memory_ids=related_memory_ids,
        )

        # 3. Update root HANDOFF.md atomically
        handoff_path = p_dir / "HANDOFF.md"
        lock_path = p_dir / ".researchos" / "handoff.lock"
        with file_lock(lock_path, timeout=5.0):
            atomic_write_text(handoff_path, body_content)

        # 4. Synchronize STATE.md
        self._sync_state_file(
            project_id=project_id,
            current_progress=current_progress or task,
            unresolved_items=unresolved_items or [],
            next_steps=next_steps or [],
            agent=agent,
            timestamp_str=now.strftime("%Y-%m-%d"),
        )

        return mem

    def get_latest_handoff(self, project_id: str) -> str:
        """Reads the latest HANDOFF.md content."""
        p_dir = self.project_svc.get_project_dir(project_id)
        handoff_path = p_dir / "HANDOFF.md"
        if not handoff_path.exists():
            raise ProjectNotFoundError(f"No HANDOFF.md found for project '{project_id}'.")
        return handoff_path.read_text(encoding="utf-8")

    def _sync_state_file(
        self,
        project_id: str,
        current_progress: str,
        unresolved_items: list[str],
        next_steps: list[str],
        agent: str,
        timestamp_str: str,
    ) -> None:
        p_dir = self.project_svc.get_project_dir(project_id)
        state_path = p_dir / "STATE.md"
        if not state_path.exists():
            return

        lock_path = p_dir / ".researchos" / "state.lock"
        with file_lock(lock_path, timeout=5.0):
            proj = self.project_svc.get_project(project_id)
            state_lines = [
                f"# Current State: {proj.project_name}",
                f"*Last Updated: {utc_now().isoformat()} by `{agent}`*",
                "",
                "## 1. 当前研究目标 (Current Goal)",
                f"- {proj.frontmatter.research_goal or 'Advance project objectives.'}",
                "",
                "## 2. 当前已知事实 (Known Facts)",
                "- See active knowledge and observations in INDEX.md.",
                "",
                "## 3. 当前研究进展 (Current Progress)",
                f"- {current_progress}",
                "",
                "## 4. 当前重要问题 (Key Questions)",
                "- Review open hypotheses.",
                "",
                "## 5. 尚未解决的问题 (Unresolved Issues)",
            ]
            if unresolved_items:
                for item in unresolved_items:
                    state_lines.append(f"- {item}")
            else:
                state_lines.append("- _None recorded._")
            state_lines.append("")

            state_lines.append("## 6. 最近的重要变化 (Recent Changes)")
            state_lines.append(f"- [{timestamp_str}] Handoff recorded by `{agent}`: {current_progress[:80]}")
            state_lines.append("")

            state_lines.append("## 7. 下一步关注事项 (Next Focus)")
            if next_steps:
                for idx, step in enumerate(next_steps, 1):
                    state_lines.append(f"{idx}. {step}")
            else:
                state_lines.append("1. Review latest handoff and continue execution.")

            atomic_write_text(state_path, "\n".join(state_lines))
