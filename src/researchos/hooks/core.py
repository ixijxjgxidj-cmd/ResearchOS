"""Memory Hook Core for automatic context restoration across agent lifecycles."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from researchos.config.settings import Settings
from researchos.core.handoff_service import HandoffService
from researchos.core.project_memory_service import ProjectMemoryService
from researchos.core.project_service import ProjectService
from researchos.core.storage_service import atomic_write_text, file_lock
from researchos.hooks.resolver import ProjectResolutionError, ProjectResolver
from researchos.models.memory import utc_now


class HookResult(BaseModel):
    """Execution outcome of a lifecycle hook event."""

    success: bool
    event: str
    project_id: str | None = None
    project_dir: str | None = None
    memory_version: int = 1
    context_text: str | None = None
    message: str | None = None
    idempotent_skip: bool = False
    error: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)


class MemoryHookCore:
    """Agent-independent Memory Hook Core managing session orientation and compaction recovery."""

    def __init__(self, vault_root: Path | str | None = None) -> None:
        self.vault_root = Settings.discover_vault_root(vault_root)
        self.resolver = ProjectResolver(self.vault_root)
        self.project_svc = ProjectService(self.vault_root)
        self.project_memory_svc = ProjectMemoryService(self.vault_root)
        self.handoff_svc = HandoffService(self.vault_root)

    def _check_idempotency(self, p_dir: Path, event: str, event_id: str | None = None) -> bool:
        """Returns True if this exact event was processed very recently (preventing loops)."""
        events_file = p_dir / ".researchos" / "hook_events.json"
        if not events_file.exists():
            return False

        try:
            data = json.loads(events_file.read_text(encoding="utf-8"))
            recent_events = data.get("recent_events", [])
            now_ts = datetime.now(UTC).timestamp()

            for item in recent_events[-10:]:
                # If explicit event_id matches
                if event_id and item.get("event_id") == event_id:
                    return True
                # If same event fired within 1.5 seconds without explicit ID
                if not event_id and item.get("event") == event:
                    ts = item.get("ts", 0)
                    if now_ts - ts < 1.5:
                        return True
            return False
        except Exception:
            return False

    def _record_event(self, p_dir: Path, event: str, event_id: str | None = None) -> None:
        """Records event execution for idempotency tracking."""
        meta_dir = p_dir / ".researchos"
        meta_dir.mkdir(parents=True, exist_ok=True)
        events_file = meta_dir / "hook_events.json"
        lock_file = meta_dir / "hook_events.lock"

        with file_lock(lock_file, timeout=5.0):
            data: dict[str, Any] = {"recent_events": []}
            if events_file.exists():
                try:
                    data = json.loads(events_file.read_text(encoding="utf-8"))
                except Exception:
                    data = {"recent_events": []}

            recent = data.get("recent_events", [])
            recent.append({
                "event": event,
                "event_id": event_id,
                "ts": datetime.now(UTC).timestamp(),
                "time": utc_now().isoformat(),
            })
            data["recent_events"] = recent[-30:]  # Keep last 30
            atomic_write_text(events_file, json.dumps(data, indent=2))

    def on_session_start(
        self,
        project_id: str | None = None,
        cwd: Path | str | None = None,
        agent_id: str | None = None,
        event_id: str | None = None,
    ) -> HookResult:
        """Event A: Agent begins a new research session.

        Identifies project, validates MEMORY.md, rebuilds if stale, and generates injection context.
        """
        try:
            pid, p_dir = self.resolver.resolve(project_id, cwd)
        except (ProjectResolutionError, Exception) as exc:
            return HookResult(
                success=False,
                event="session_start",
                error=str(exc),
                message=f"Failed to resolve research project: {exc}",
            )

        if self._check_idempotency(p_dir, "session_start", event_id):
            mem_text = self.project_memory_svc.get_project_memory(pid)
            return HookResult(
                success=True,
                event="session_start",
                project_id=pid,
                project_dir=str(p_dir),
                context_text=mem_text,
                idempotent_skip=True,
                message="Session start already initialized (idempotent).",
            )

        # Ensure MEMORY.md is current
        mem_text = self.project_memory_svc.refresh_project_memory_if_stale(pid)
        self._record_event(p_dir, "session_start", event_id)

        injection_context = (
            f"> [!IMPORTANT] ResearchOS Always-on Memory: Session Initialized\n"
            f"> **Project**: `{pid}` | **Executing Agent**: `{agent_id or 'research-agent'}`\n\n"
            f"{mem_text}\n"
        )

        return HookResult(
            success=True,
            event="session_start",
            project_id=pid,
            project_dir=str(p_dir),
            context_text=injection_context,
            message=f"Successfully initialized research context for '{pid}'.",
        )

    def on_pre_compaction(
        self,
        project_id: str | None = None,
        cwd: Path | str | None = None,
        agent_id: str | None = None,
        task: str | None = None,
        completed_work: list[str] | None = None,
        current_progress: str | None = None,
        next_steps: list[str] | None = None,
        blockers: list[str] | None = None,
        event_id: str | None = None,
    ) -> HookResult:
        """Event B: Before context compaction.

        Records shift state, updates STATE.md and HANDOFF.md, and refreshes MEMORY.md snapshot.
        """
        try:
            pid, p_dir = self.resolver.resolve(project_id, cwd)
        except (ProjectResolutionError, Exception) as exc:
            return HookResult(
                success=False,
                event="pre_compaction",
                error=str(exc),
                message=f"Failed to resolve research project: {exc}",
            )

        if self._check_idempotency(p_dir, "pre_compaction", event_id):
            return HookResult(
                success=True,
                event="pre_compaction",
                project_id=pid,
                project_dir=str(p_dir),
                idempotent_skip=True,
                message="Pre-compaction state already saved (idempotent).",
            )

        # Record handoff if task or progress provided
        if task or completed_work or next_steps or current_progress:
            self.handoff_svc.create_handoff(
                project_id=pid,
                task=task or "Context Compaction Checkpoint",
                completed_work=completed_work,
                current_progress=current_progress,
                issues_encountered=blockers,
                next_steps=next_steps,
                agent_id=agent_id or "pre-compaction-hook",
            )

        # Refresh MEMORY.md
        mem_text = self.project_memory_svc.rebuild_project_memory(pid, preserve_custom_notes=True)
        self._record_event(p_dir, "pre_compaction", event_id)

        return HookResult(
            success=True,
            event="pre_compaction",
            project_id=pid,
            project_dir=str(p_dir),
            context_text=mem_text,
            message=f"Successfully captured pre-compaction state for '{pid}'.",
        )

    def on_post_compaction(
        self,
        project_id: str | None = None,
        cwd: Path | str | None = None,
        agent_id: str | None = None,
        event_id: str | None = None,
    ) -> HookResult:
        """Event C: After context compaction (CORE).

        Automatically re-identifies project, verifies memory version, rebuilds if stale,
        and generates injection context to restore working memory.
        """
        try:
            pid, p_dir = self.resolver.resolve(project_id, cwd)
        except (ProjectResolutionError, Exception) as exc:
            return HookResult(
                success=False,
                event="post_compaction",
                error=str(exc),
                message=f"Failed to resolve research project: {exc}",
            )

        # Refresh MEMORY.md if stale
        mem_text = self.project_memory_svc.refresh_project_memory_if_stale(pid)
        self._record_event(p_dir, "post_compaction", event_id)

        restoration_text = (
            f"# [ResearchOS Context Restored After Compaction]\n"
            f"> **Project**: `{pid}` | **Agent**: `{agent_id or 'active-agent'}`\n"
            f"> **Notice**: Context compaction occurred. Long-term research state, fixed constraints, "
            f"and next actions have been automatically re-hydrated from `MEMORY.md`.\n\n"
            f"{mem_text}\n"
        )

        return HookResult(
            success=True,
            event="post_compaction",
            project_id=pid,
            project_dir=str(p_dir),
            context_text=restoration_text,
            message=f"Working memory successfully restored for project '{pid}'.",
        )

    def on_session_end(
        self,
        project_id: str | None = None,
        cwd: Path | str | None = None,
        agent_id: str | None = None,
        task: str | None = None,
        completed_work: list[str] | None = None,
        next_steps: list[str] | None = None,
        event_id: str | None = None,
    ) -> HookResult:
        """Event D: Session termination or active handoff."""
        try:
            pid, p_dir = self.resolver.resolve(project_id, cwd)
        except (ProjectResolutionError, Exception) as exc:
            return HookResult(
                success=False,
                event="session_end",
                error=str(exc),
                message=f"Failed to resolve research project: {exc}",
            )

        if task or completed_work or next_steps:
            self.handoff_svc.create_handoff(
                project_id=pid,
                task=task or "Session Conclusion",
                completed_work=completed_work,
                next_steps=next_steps,
                agent_id=agent_id or "session-end-hook",
            )

        mem_text = self.project_memory_svc.rebuild_project_memory(pid, preserve_custom_notes=True)
        self._record_event(p_dir, "session_end", event_id)

        return HookResult(
            success=True,
            event="session_end",
            project_id=pid,
            project_dir=str(p_dir),
            context_text=mem_text,
            message=f"Session finalized and MEMORY.md refreshed for project '{pid}'.",
        )
