"""Antigravity / Gemini CLI hook adapter supporting context injection and lifecycle resumption."""

from typing import Any

from researchos.hooks.adapters.base import BaseHookAdapter
from researchos.hooks.core import HookResult


class GeminiAntigravityAdapter(BaseHookAdapter):
    """Adapter for Google Antigravity IDE and Gemini CLI agents."""

    @property
    def agent_name(self) -> str:
        return "antigravity"

    def handle_session_start(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> str:
        """Handles session boot for Antigravity agents."""
        res: HookResult = self.core.on_session_start(
            project_id=project_id,
            cwd=cwd,
            agent_id="antigravity",
            event_id=kwargs.get("event_id"),
        )
        return self._render_injection(res)

    def handle_pre_compaction(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> str:
        """Handles pre-compaction hook for Antigravity agents."""
        res: HookResult = self.core.on_pre_compaction(
            project_id=project_id,
            cwd=cwd,
            agent_id="antigravity",
            task=kwargs.get("task"),
            completed_work=kwargs.get("completed_work"),
            current_progress=kwargs.get("current_progress"),
            next_steps=kwargs.get("next_steps"),
            blockers=kwargs.get("blockers"),
            event_id=kwargs.get("event_id"),
        )
        return res.message or "Pre-compaction state saved."

    def handle_post_compaction(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> str:
        """Handles post-compaction context recovery for Antigravity agents (Event C CORE)."""
        res: HookResult = self.core.on_post_compaction(
            project_id=project_id,
            cwd=cwd,
            agent_id="antigravity",
            event_id=kwargs.get("event_id"),
        )
        return self._render_injection(res)

    def handle_session_end(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> str:
        """Handles Antigravity session conclusion and handoff."""
        res: HookResult = self.core.on_session_end(
            project_id=project_id,
            cwd=cwd,
            agent_id="antigravity",
            task=kwargs.get("task"),
            completed_work=kwargs.get("completed_work"),
            next_steps=kwargs.get("next_steps"),
            event_id=kwargs.get("event_id"),
        )
        return res.message or "Session state saved."

    def _render_injection(self, res: HookResult) -> str:
        if not res.success:
            return f"> [!WARNING] ResearchOS Hook Error: {res.error}\n"
        return res.context_text or ""
