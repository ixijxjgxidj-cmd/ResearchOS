"""ResearchOS Memory Hooks architecture for cross-session and compaction recovery."""

from researchos.hooks.adapters.antigravity import GeminiAntigravityAdapter
from researchos.hooks.adapters.base import BaseHookAdapter
from researchos.hooks.adapters.claude_code import ClaudeCodeAdapter
from researchos.hooks.adapters.codex import CodexAdapter
from researchos.hooks.adapters.generic_cli import GenericCLIAdapter
from researchos.hooks.core import HookResult, MemoryHookCore
from researchos.hooks.resolver import ProjectResolutionError, ProjectResolver

__all__ = [
    "MemoryHookCore",
    "HookResult",
    "ProjectResolver",
    "ProjectResolutionError",
    "BaseHookAdapter",
    "ClaudeCodeAdapter",
    "GeminiAntigravityAdapter",
    "CodexAdapter",
    "GenericCLIAdapter",
]
