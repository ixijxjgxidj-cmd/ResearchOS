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
    schema_version: int = Field(default=2, description="Default schema version.")
    lock_timeout_seconds: float = Field(default=10.0, description="Lock timeout in seconds.")
    auto_create_dirs: bool = Field(default=True, description="Automatically create vault subdirectories.")

    @classmethod
    def discover_vault_root(cls, explicit_path: str | Path | None = None) -> Path:
        """Discovers the vault root using explicit path, environment variable, or directory search."""
        if explicit_path:
            p = Path(explicit_path).resolve()
            return p

        env_root = os.environ.get("RESEARCH_VAULT_ROOT")
        if env_root:
            return Path(env_root).resolve()

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
