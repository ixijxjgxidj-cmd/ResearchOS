"""Generic CLI hook adapter for shell scripts, IDE sidecars, and terminal workflows."""

import json
from typing import Any

from researchos.hooks.adapters.base import BaseHookAdapter
from researchos.hooks.core import HookResult


class GenericCLIAdapter(BaseHookAdapter):
    """Universal CLI adapter for any terminal, shell hook, or agent runner."""

    @property
    def agent_name(self) -> str:
        return "generic_cli"

    def handle_session_start(self, project_id: str | None = None, cwd: str | None = None, as_json: bool = False, **kwargs: Any) -> str:
        res: HookResult = self.core.on_session_start(
            project_id=project_id,
            cwd=cwd,
            agent_id=kwargs.get("agent_id", "cli-agent"),
            event_id=kwargs.get("event_id"),
        )
        return self._format(res, as_json)

    def handle_pre_compaction(self, project_id: str | None = None, cwd: str | None = None, as_json: bool = False, **kwargs: Any) -> str:
        res: HookResult = self.core.on_pre_compaction(
            project_id=project_id,
            cwd=cwd,
            agent_id=kwargs.get("agent_id", "cli-agent"),
            task=kwargs.get("task"),
            completed_work=kwargs.get("completed_work"),
            current_progress=kwargs.get("current_progress"),
            next_steps=kwargs.get("next_steps"),
            blockers=kwargs.get("blockers"),
            event_id=kwargs.get("event_id"),
        )
        return self._format(res, as_json)

    def handle_post_compaction(self, project_id: str | None = None, cwd: str | None = None, as_json: bool = False, **kwargs: Any) -> str:
        res: HookResult = self.core.on_post_compaction(
            project_id=project_id,
            cwd=cwd,
            agent_id=kwargs.get("agent_id", "cli-agent"),
            event_id=kwargs.get("event_id"),
        )
        return self._format(res, as_json)

    def handle_session_end(self, project_id: str | None = None, cwd: str | None = None, as_json: bool = False, **kwargs: Any) -> str:
        res: HookResult = self.core.on_session_end(
            project_id=project_id,
            cwd=cwd,
            agent_id=kwargs.get("agent_id", "cli-agent"),
            task=kwargs.get("task"),
            completed_work=kwargs.get("completed_work"),
            next_steps=kwargs.get("next_steps"),
            event_id=kwargs.get("event_id"),
        )
        return self._format(res, as_json)

    def _format(self, res: HookResult, as_json: bool) -> str:
        if as_json:
            return json.dumps(res.model_dump(mode="json"), indent=2)
        if not res.success:
            return f"[ERROR] {res.error}"
        return res.context_text or res.message or "OK"
