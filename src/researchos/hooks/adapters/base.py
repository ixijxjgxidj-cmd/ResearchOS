"""Base adapter interface for agent-specific hook implementations."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from researchos.hooks.core import HookResult, MemoryHookCore


class BaseHookAdapter(ABC):
    """Abstract base class for all agent-specific hook adapters."""

    def __init__(self, vault_root: Path | str | None = None) -> None:
        self.core = MemoryHookCore(vault_root)

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Returns the identifier of the supported agent."""
        pass

    @abstractmethod
    def handle_session_start(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> Any:
        """Dispatches and formats session start for the host agent."""
        pass

    @abstractmethod
    def handle_pre_compaction(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> Any:
        """Dispatches and formats pre-compaction state save for the host agent."""
        pass

    @abstractmethod
    def handle_post_compaction(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> Any:
        """Dispatches and formats post-compaction memory restoration for the host agent."""
        pass

    @abstractmethod
    def handle_session_end(self, project_id: str | None = None, cwd: str | None = None, **kwargs: Any) -> Any:
        """Dispatches and formats session end / handoff for the host agent."""
        pass
