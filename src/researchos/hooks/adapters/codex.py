"""OpenAI Codex and OpenAI CLI hook adapter."""

from typing import Any

from researchos.hooks.adapters.base import BaseHookAdapter
from researchos.hooks.core import HookResult


class CodexAdapter(BaseHookAdapter):
    """Adapter for OpenAI Codex, OpenAI CLI, and Python agent wrappers."""

    @property
    def agent_name(self) -> str:
        return "codex"

    def handle_session_start(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> dict[str, Any]:
        res: HookResult = self.core.on_session_start(
            project_id=project_id,
            cwd=cwd,
            agent_id="openai-codex",
            event_id=kwargs.get("event_id"),
        )
        return self._format(res)

    def handle_pre_compaction(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> dict[str, Any]:
        res: HookResult = self.core.on_pre_compaction(
            project_id=project_id,
            cwd=cwd,
            agent_id="openai-codex",
            task=kwargs.get("task"),
            completed_work=kwargs.get("completed_work"),
            current_progress=kwargs.get("current_progress"),
            next_steps=kwargs.get("next_steps"),
            blockers=kwargs.get("blockers"),
            event_id=kwargs.get("event_id"),
        )
        return self._format(res)

    def handle_post_compaction(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> dict[str, Any]:
        res: HookResult = self.core.on_post_compaction(
            project_id=project_id,
            cwd=cwd,
            agent_id="openai-codex",
            event_id=kwargs.get("event_id"),
        )
        return self._format(res)

    def handle_session_end(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> dict[str, Any]:
        res: HookResult = self.core.on_session_end(
            project_id=project_id,
            cwd=cwd,
            agent_id="openai-codex",
            task=kwargs.get("task"),
            completed_work=kwargs.get("completed_work"),
            next_steps=kwargs.get("next_steps"),
            event_id=kwargs.get("event_id"),
        )
        return self._format(res)

    def _format(self, res: HookResult) -> dict[str, Any]:
        return {
            "success": res.success,
            "event": res.event,
            "project_id": res.project_id,
            "context_text": res.context_text,
            "message": res.message,
            "error": res.error,
        }
