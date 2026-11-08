"""Configuration and environment settings for ResearchOS."""

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Runtime configuration for ResearchOS."""

    vault_root: Path = Field(
        default_factory=lambda: Settings.discover_vault_root(),
        description="Root path of the ResearchVault.",
    )
    schema_version: int = Field(default=2, description="Default schema version.")
    lock_timeout_seconds: float = Field(default=10.0, description="Lock timeout in seconds.")
    auto_create_dirs: bool = Field(default=True, description="Automatically create vault subdirectories.")

    @classmethod
    def discover_vault_root(cls, explicit_path: str | Path | None = None) -> Path:
        """Discovers the vault root using explicit path, environment variables, or directory search.

        Precedence:
            1. explicit_path (CLI or function argument)
            2. RESEARCH_VAULT_ROOT (Primary environment variable)
            3. VAULT_PATH (Compatibility environment variable)
            4. RESEARCHOS_VAULT_ROOT (Legacy environment variable)
            5. Filesystem auto-discovery (.researchos, ResearchVault)
            6. Working directory fallback
        """
        if explicit_path:
            p = Path(explicit_path).resolve()
            return p

        # Check environment variables in priority order
        for env_var in ("RESEARCH_VAULT_ROOT", "VAULT_PATH", "RESEARCHOS_VAULT_ROOT"):
            val = os.environ.get(env_var)
            if val and val.strip():
                return Path(val.strip()).resolve()

        cwd = Path.cwd().resolve()

        # Check if ResearchVault folder exists directly in cwd
        if (cwd / "ResearchVault").is_dir():
            return (cwd / "ResearchVault").resolve()

        # Check upward search
        curr = cwd
        while curr != curr.parent:
            if (curr / "ResearchVault").is_dir():
                return (curr / "ResearchVault").resolve()
            if (curr / ".researchos").exists() or (curr / "00-Projects").exists():
                return curr
            curr = curr.parent

        # Default fallback: prefer ResearchVault subfolder if cwd is repository root, or cwd
        if (cwd / "src" / "researchos").exists():
            rv = cwd / "ResearchVault"
            rv.mkdir(parents=True, exist_ok=True)
            return rv.resolve()

        return cwd

    @staticmethod
    def get_mcp_transport(explicit: str | None = None) -> Literal["stdio", "sse"]:
        """Resolves MCP transport mode.

        Precedence: explicit > MCP_TRANSPORT env var > 'stdio'
        """
        if explicit:
            val = explicit.lower().strip()
            return "sse" if val == "sse" else "stdio"
        env = os.environ.get("MCP_TRANSPORT", "").lower().strip()
        if env == "sse":
            return "sse"
        return "stdio"

    @staticmethod
    def get_mcp_port(explicit: int | None = None) -> int:
        """Resolves MCP listening port.

        Precedence: explicit > PORT env var > MCP_PORT env var > 8000
        """
        if explicit is not None:
            return explicit
        for env_name in ("PORT", "MCP_PORT"):
            val = os.environ.get(env_name)
            if val and val.strip().isdigit():
                return int(val.strip())
        return 8000

    @staticmethod
    def get_mcp_host(explicit: str | None = None) -> str:
        """Resolves MCP listening host.

        Precedence: explicit > MCP_HOST env var > HOST env var > '0.0.0.0'
        """
        if explicit:
            return explicit.strip()
        for env_name in ("MCP_HOST", "HOST"):
            val = os.environ.get(env_name)
            if val and val.strip():
                return val.strip()
        return "0.0.0.0"

    @staticmethod
    def get_log_level(explicit: str | None = None) -> str:
        """Resolves logging level.

        Precedence: explicit > LOG_LEVEL env var > 'INFO'
        """
        if explicit:
            return explicit.upper().strip()
        return os.environ.get("LOG_LEVEL", "INFO").upper().strip()

    @staticmethod
    def get_mcp_profile(explicit: str | None = None) -> Literal["lite", "advanced"]:
        """Resolves MCP tool exposure profile (lite=6 core tools, advanced=all tools).

        Precedence: explicit > RESEARCHOS_PROFILE env var > 'lite'
        """
        if explicit:
            val = explicit.lower().strip()
            return "advanced" if val == "advanced" else "lite"
        env = (os.environ.get("RESEARCHOS_PROFILE") or os.environ.get("MCP_PROFILE") or "").lower().strip()
        if env == "advanced":
            return "advanced"
        return "lite"
