"""Project resolver for determining the active research project boundary without ambiguity."""

import json
import os
from pathlib import Path

from researchos.core.storage_service import parse_frontmatter
from researchos.utils.exceptions import ProjectNotFoundError, ResearchOSError, ValidationError


class ProjectResolutionError(ProjectNotFoundError):
    """Raised when the active research project cannot be deterministically resolved."""
    pass


class ProjectResolver:
    """Resolves current research project directory and ID with strict priority and zero guessing."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()

    def resolve(
        self,
        project_id: str | None = None,
        cwd: Path | str | None = None,
    ) -> tuple[str, Path]:
        """Resolves (project_id, project_dir).

        Precedence:
            1. Explicit project_id argument
            2. Environment variables: RESEARCHOS_PROJECT_ID, PROJECT_ID
            3. Upward directory tree search from cwd for PROJECT.md / .researchos / MEMORY.md
            4. Mapped configuration (projects_map.json)
        
        Strict safety:
            - If unresolvable or ambiguous, raises ProjectResolutionError.
            - Never guesses or selects an arbitrary project from vault.
        """
        # 1. Explicit project_id argument
        target_pid = project_id.strip() if project_id and project_id.strip() else None

        # 2. Environment variables
        if not target_pid:
            for env_name in ("RESEARCHOS_PROJECT_ID", "PROJECT_ID"):
                val = os.environ.get(env_name)
                if val and val.strip():
                    target_pid = val.strip()
                    break

        if target_pid:
            clean_id = target_pid.lower()
            candidate_dir = self.vault_root / clean_id
            if candidate_dir.is_dir() and (candidate_dir / "PROJECT.md").exists():
                return clean_id, candidate_dir

            # Check if target_pid is an actual directory path
            direct_path = Path(target_pid).resolve()
            if direct_path.is_dir() and (direct_path / "PROJECT.md").exists():
                meta, _ = parse_frontmatter((direct_path / "PROJECT.md").read_text(encoding="utf-8"))
                resolved_id = str(meta.get("project_id", direct_path.name)).lower()
                return resolved_id, direct_path

            raise ProjectResolutionError(
                f"Specified project '{target_pid}' not found in vault '{self.vault_root}'."
            )

        # 3. Upward search from cwd
        start_dir = Path(cwd or Path.cwd()).resolve()
        curr = start_dir
        while curr != curr.parent:
            proj_file = curr / "PROJECT.md"
            if proj_file.is_file():
                try:
                    meta, _ = parse_frontmatter(proj_file.read_text(encoding="utf-8"))
                    resolved_id = str(meta.get("project_id", curr.name)).lower()
                    return resolved_id, curr
                except Exception:
                    return curr.name.lower(), curr

            if (curr / ".researchos").is_dir() and (curr / "MEMORY.md").is_file():
                return curr.name.lower(), curr

            curr = curr.parent

        # 4. Mapped configuration in ~/.researchos/projects_map.json or vault/.researchos/projects_map.json
        for map_file in [
            self.vault_root / ".researchos" / "projects_map.json",
            Path.home() / ".researchos" / "projects_map.json",
        ]:
            if map_file.is_file():
                try:
                    mapping = json.loads(map_file.read_text(encoding="utf-8"))
                    str_start = str(start_dir)
                    for dir_pattern, pid in mapping.items():
                        if str_start.startswith(str(Path(dir_pattern).resolve())):
                            clean_pid = str(pid).lower()
                            candidate = self.vault_root / clean_pid
                            if candidate.is_dir():
                                return clean_pid, candidate
                except Exception:
                    pass

        # Strict isolation: fail clearly rather than guessing
        raise ProjectResolutionError(
            f"Unable to deterministically resolve ResearchOS project from directory '{start_dir}'. "
            "Please explicitly specify project_id or ensure working directory is within a project folder."
        )
