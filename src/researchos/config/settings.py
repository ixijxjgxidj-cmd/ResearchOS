"""Configuration and environment settings for ResearchOS."""

import os
from pathlib import Path
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Runtime configuration for ResearchOS."""

    vault_root: Path = Field(
        default_factory=lambda: Settings.discover_vault_root(),
        description="Root path of the ResearchVault.",
    )
    schema_version: int = Field(default=1, description="Default schema version.")
    lock_timeout_seconds: float = Field(default=10.0, description="Lock timeout in seconds.")
    auto_create_dirs: bool = Field(default=True, description="Automatically create vault subdirectories.")

    @classmethod
    def discover_vault_root(cls, explicit_path: str | Path | None = None) -> Path:
        """Discovers the vault root using explicit path, environment variable, or upward search."""
        if explicit_path:
            p = Path(explicit_path).resolve()
            return p

        env_root = os.environ.get("RESEARCH_VAULT_ROOT")
        if env_root:
            return Path(env_root).resolve()

        cwd = Path.cwd().resolve()
        curr = cwd
        while curr != curr.parent:
            if (curr / ".researchos").exists() or (curr / "00-Projects").exists():
                return curr
            curr = curr.parent

        # Default fallback to current working directory
        return cwd
