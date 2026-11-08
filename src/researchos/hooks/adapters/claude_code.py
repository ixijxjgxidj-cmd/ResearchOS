"""Claude Code hook adapter supporting Claude Code hooks and context injection."""

import json
from typing import Any

from researchos.hooks.adapters.base import BaseHookAdapter
from researchos.hooks.core import HookResult


class ClaudeCodeAdapter(BaseHookAdapter):
    """Adapter for Claude Code CLI and Anthropic hook protocol."""

    @property
    def agent_name(self) -> str:
        return "claude_code"

    def handle_session_start(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """Handles Claude Code session start hook."""
        res: HookResult = self.core.on_session_start(
            project_id=project_id,
            cwd=cwd,
            agent_id="claude-code",
            event_id=kwargs.get("event_id"),
        )
        return self._format_response("session_start", res)

    def handle_pre_compaction(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """Handles Claude Code pre-compaction hook."""
        res: HookResult = self.core.on_pre_compaction(
            project_id=project_id,
            cwd=cwd,
            agent_id="claude-code",
            task=kwargs.get("task"),
            completed_work=kwargs.get("completed_work"),
            current_progress=kwargs.get("current_progress"),
            next_steps=kwargs.get("next_steps"),
            blockers=kwargs.get("blockers"),
            event_id=kwargs.get("event_id"),
        )
        return self._format_response("pre_compaction", res)

    def handle_post_compaction(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """Handles Claude Code post-compaction hook (Event C CORE).

        Injects restored working memory and next actions via additionalContext.
        """
        res: HookResult = self.core.on_post_compaction(
            project_id=project_id,
            cwd=cwd,
            agent_id="claude-code",
            event_id=kwargs.get("event_id"),
        )
        return self._format_response("post_compaction", res)

    def handle_session_end(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """Handles Claude Code session end or /exit hook."""
        res: HookResult = self.core.on_session_end(
            project_id=project_id,
            cwd=cwd,
            agent_id="claude-code",
            task=kwargs.get("task"),
            completed_work=kwargs.get("completed_work"),
            next_steps=kwargs.get("next_steps"),
            event_id=kwargs.get("event_id"),
        )
        return self._format_response("session_end", res)

    def handle_user_prompt_fallback(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """Fallback mechanism for frameworks that only support UserPromptSubmit hooks.

        Checks if MEMORY.md was modified or context was recently compacted, and injects context before user message.
        """
        res: HookResult = self.core.on_session_start(
            project_id=project_id,
            cwd=cwd,
            agent_id="claude-code",
            event_id=kwargs.get("event_id"),
        )
        return self._format_response("user_prompt_fallback", res)

    def _format_response(self, hook_name: str, res: HookResult) -> dict[str, Any]:
        if not res.success:
            return {
                "status": "error",
                "hook": hook_name,
                "error": res.error,
                "message": res.message,
            }

        return {
            "status": "success",
            "hook": hook_name,
            "project_id": res.project_id,
            "project_dir": res.project_dir,
            "additionalContext": res.context_text,
            "systemPromptExtension": res.context_text,
            "message": res.message,
            "idempotent_skip": res.idempotent_skip,
        }
