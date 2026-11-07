"""Markdown-first and filesystem-first persistence store for ResearchOS entities."""

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, TypeVar

from researchos.core.enums import (
    ExperimentStatus,
    IdPrefix,
    ProjectStatus,
)
from researchos.core.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    PathSecurityError,
    ValidationError,
    VersionConflictError,
)
from researchos.core.ids import validate_id
from researchos.core.models import (
    Artifact,
    BaseResearchEntity,
    Claim,
    Decision,
    Experiment,
    Finding,
    Paper,
    Project,
    Run,
    utc_now,
)
from researchos.storage.atomic_writer import atomic_write_text
from researchos.storage.file_lock import file_lock
from researchos.storage.frontmatter import dump_frontmatter, parse_frontmatter
from researchos.storage.link_resolver import validate_vault_path

T = TypeVar("T", bound=BaseResearchEntity)


class MarkdownStore:
    """Manages reading, writing, and scanning Markdown documents in the ResearchVault."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()

    def get_project_dir(self, project_id: str) -> Path:
        validate_id(project_id)
        return validate_vault_path(self.vault_root, Path("00-Projects") / project_id)

    def resolve_entity_path(self, entity_id: str, project_id: str | None = None) -> Path:
        """Determines the standard filesystem path for a given entity ID."""
        prefix, _, _ = validate_id(entity_id)

        if prefix == IdPrefix.PROJECT:
            return self.get_project_dir(entity_id) / "PROJECT.md"

        if prefix == IdPrefix.PAPER:
            return validate_vault_path(self.vault_root, Path("01-Literature") / f"{entity_id}.md")

        # For experiment, run, finding, claim, decision, we need project_id
        if not project_id:
            # Try to search for it across all projects in the vault
            found = self.find_entity_path_by_id(entity_id)
            if found:
                return found
            raise EntityNotFoundError(
                f"Cannot resolve path for {entity_id}: project_id is required."
            )

        proj_dir = self.get_project_dir(project_id)
        if prefix == IdPrefix.EXPERIMENT:
            return proj_dir / "Experiments" / f"{entity_id}.md"
        elif prefix == IdPrefix.RUN:
            return proj_dir / "Runs" / f"{entity_id}.md"
        elif prefix == IdPrefix.FINDING:
            return proj_dir / "Findings" / f"{entity_id}.md"
        elif prefix == IdPrefix.CLAIM:
            return proj_dir / "Claims" / f"{entity_id}.md"
        elif prefix == IdPrefix.DECISION:
            return proj_dir / "Decisions" / f"{entity_id}.md"
        elif prefix == IdPrefix.ARTIFACT:
            return proj_dir / "Artifacts" / f"{entity_id}.md"
        else:
            raise ValidationError(f"Unsupported entity prefix '{prefix}'.")

    def find_entity_path_by_id(self, entity_id: str) -> Path | None:
        """Scans the vault to find the file corresponding to entity_id."""
        prefix, _, _ = validate_id(entity_id)
        if prefix == IdPrefix.PROJECT:
            path = self.get_project_dir(entity_id) / "PROJECT.md"
            return path if path.exists() else None

        if prefix == IdPrefix.PAPER:
            path = self.vault_root / "01-Literature" / f"{entity_id}.md"
            return path if path.exists() else None

        # Search within 00-Projects
        projects_dir = self.vault_root / "00-Projects"
        if not projects_dir.exists():
            return None

        target_name = f"{entity_id}.md"
        for p in projects_dir.rglob(target_name):
            if p.is_file():
                return p.resolve()
        return None

    def read_entity_raw(self, path: Path | str) -> tuple[dict[str, Any], str]:
        p = Path(path).resolve()
        if not p.exists():
            raise EntityNotFoundError(f"File not found: {p}")
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
        return parse_frontmatter(content)

    def write_entity_raw(
        self,
        path: Path | str,
        metadata: dict[str, Any],
        body: str,
        expected_updated_at: datetime | None = None,
    ) -> Path:
        """Writes metadata and body to file, enforcing optimistic concurrency."""
        p = Path(path).resolve()
        validate_vault_path(self.vault_root, p)

        lock_path = self.vault_root / ".researchos" / "locks" / f"{p.name}.lock"
        with file_lock(lock_path, timeout=10.0):
            if p.exists() and expected_updated_at is not None:
                existing_meta, _ = self.read_entity_raw(p)
                existing_updated = existing_meta.get("updated_at")
                if existing_updated:
                    if isinstance(existing_updated, str):
                        try:
                            existing_dt = datetime.fromisoformat(existing_updated)
                        except Exception:
                            existing_dt = None
                    elif isinstance(existing_updated, datetime):
                        existing_dt = existing_updated
                    else:
                        existing_dt = None

                    if existing_dt:
                        # Compare normalized ISO strings or timestamps
                        if abs((existing_dt - expected_updated_at).total_seconds()) > 0.001:
                            raise VersionConflictError(
                                f"Version conflict writing {p.name}. "
                                f"Expected {expected_updated_at.isoformat()}, found {existing_dt.isoformat()}.",
                                file_path=str(p),
                                expected_version=expected_updated_at.isoformat(),
                                actual_version=existing_dt.isoformat(),
                            )

            metadata["updated_at"] = utc_now()
            content = dump_frontmatter(metadata, body)
            return atomic_write_text(p, content)

    def format_title_header(self, entity: BaseResearchEntity, body: str) -> str:
        """Ensures the H1 header reflects whether the entity is pending/uncompleted ('（未结项）')."""
        lines = body.splitlines()
        first_h1_idx = -1
        for idx, line in enumerate(lines):
            if line.startswith("# "):
                first_h1_idx = idx
                break

        is_pending = False
        base_title = ""
        if isinstance(entity, Project):
            is_pending = entity.status != ProjectStatus.COMPLETED
            base_title = entity.name
        elif isinstance(entity, Experiment):
            is_pending = entity.status not in (ExperimentStatus.COMPLETED, ExperimentStatus.ABANDONED)
            base_title = f"{entity.id} {entity.title}"
        elif isinstance(entity, Run):
            base_title = f"{entity.id} {entity.agent_name} Execution"
        elif isinstance(entity, Paper):
            base_title = entity.title
        elif isinstance(entity, Finding):
            base_title = f"{entity.id} {entity.title}"
        elif isinstance(entity, Claim):
            base_title = f"{entity.id} {entity.text[:60]}"
        elif isinstance(entity, Decision):
            base_title = f"{entity.id} {entity.title}"
        elif isinstance(entity, Artifact):
            base_title = f"{entity.id} {entity.name}"
        else:
            base_title = getattr(entity, "title", entity.id)

        target_h1 = f"# {base_title}（未结项）" if is_pending else f"# {base_title}"

        if first_h1_idx != -1:
            lines[first_h1_idx] = target_h1
            return "\n".join(lines)
        else:
            return f"{target_h1}\n\n{body}"

    def save_entity(
        self,
        entity: BaseResearchEntity,
        body: str,
        path: Path | str | None = None,
        expected_updated_at: datetime | None = None,
    ) -> Path:
        """Saves a domain model entity into Markdown format."""
        if path is None:
            proj_id = getattr(entity, "project_id", None)
            path = self.resolve_entity_path(entity.id, project_id=proj_id)

        formatted_body = self.format_title_header(entity, body)
        meta_dict = entity.model_dump(mode="json")
        return self.write_entity_raw(path, meta_dict, formatted_body, expected_updated_at=expected_updated_at)

    def load_entity(self, path: Path | str, model_cls: type[T]) -> tuple[T, str]:
        """Loads a Markdown file into a domain model entity and body text."""
        metadata, body = self.read_entity_raw(path)
        try:
            entity = model_cls.model_validate(metadata)
            return entity, body
        except Exception as exc:
            raise ValidationError(f"Failed to validate {path} as {model_cls.__name__}: {exc}") from exc
