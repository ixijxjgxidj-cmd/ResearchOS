"""Universal memory service for creating, reading, updating, superseding, and archiving memories."""

from pathlib import Path

from researchos.core.project_service import SUBDIRS, TYPE_TO_DIR, ProjectService
from researchos.core.storage_service import (
    atomic_write_text,
    dump_frontmatter,
    file_lock,
    parse_frontmatter,
)
from researchos.models.memory import (
    Memory,
    MemoryFrontmatter,
    MemoryStatus,
    MemoryType,
    SourceType,
    utc_now,
)
from researchos.utils.exceptions import (
    EntityAlreadyExistsError,
    MemoryNotFoundError,
    ProjectNotFoundError,
    ValidationError,
)
from researchos.utils.ids import MemoryIdGenerator
from researchos.utils.sanitizer import sanitize_markdown_text

DEFAULT_CONFIDENCE_MAP = {
    MemoryType.OBSERVATION: 0.90,
    MemoryType.NEGATIVE: 0.95,
    MemoryType.DECISION: 0.90,
    MemoryType.KNOWLEDGE: 0.85,
    MemoryType.HYPOTHESIS: 0.50,
    MemoryType.REFERENCE: 0.80,
    MemoryType.HANDOFF: 0.90,
}


class MemoryService:
    """Manages universal memory lifecycles inside isolated project directories."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.project_svc = ProjectService(self.vault_root)

    def _get_project_dir(self, project_id: str) -> Path:
        return self.project_svc.get_project_dir(project_id)

    def _find_memory_path(self, project_id: str, memory_id: str) -> Path | None:
        """Locates the memory file inside any subdirectory of the project."""
        p_dir = self._get_project_dir(project_id)
        target_name = f"{memory_id}.md"

        for sub in SUBDIRS:
            candidate = p_dir / sub / target_name
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def add_memory(
        self,
        project_id: str,
        type: MemoryType | str,
        title: str,
        content: str,
        tags: list[str] | None = None,
        source_type: SourceType | str | None = None,
        source_agent: str | None = None,
        source_skill: str | None = None,
        source_ref: str | None = None,
        related_memory_ids: list[str] | None = None,
        confidence: float | None = None,
        supersedes: str | None = None,
        superseded_by: str | None = None,
        experiment_id: str | None = None,
        paper_section: str | None = None,
        metrics_summary: str | None = None,
        parent_experiment: str | None = None,
        artifact_paths: list[str] | None = None,
    ) -> Memory:
        """Atomically adds a new memory with generated ID, frontmatter, and updates index."""
        if not title or not title.strip():
            raise ValidationError("Memory title cannot be empty.")

        # Ensure project exists
        p_dir = self._get_project_dir(project_id)
        if not (p_dir / "PROJECT.md").exists():
            raise ProjectNotFoundError(f"Project '{project_id}' does not exist.")

        # Validate type
        if isinstance(type, str):
            try:
                mem_type = MemoryType(type.lower().strip())
            except ValueError:
                raise ValidationError(
                    f"Invalid memory type '{type}'. Allowed types: {[t.value for t in MemoryType]}"
                )
        else:
            mem_type = type

        # Validate or default source_type
        resolved_source_type: SourceType | str | None = None
        if source_type:
            if isinstance(source_type, SourceType):
                resolved_source_type = source_type
            else:
                st_str = str(source_type).lower().strip()
                try:
                    resolved_source_type = SourceType(st_str)
                except ValueError:
                    resolved_source_type = st_str
        else:
            if source_agent:
                resolved_source_type = SourceType.AGENT
            elif source_ref and ("run" in source_ref.lower() or "job" in source_ref.lower() or "exp" in source_ref.lower()):
                resolved_source_type = SourceType.EXPERIMENT
            else:
                resolved_source_type = SourceType.AGENT

        # Evidence conditionality check: recommend/ensure source_ref for empirical findings
        resolved_source_ref = source_ref
        if not resolved_source_ref and mem_type in (
            MemoryType.OBSERVATION,
            MemoryType.NEGATIVE,
            MemoryType.DECISION,
        ):
            if source_agent:
                resolved_source_ref = f"agent:{source_agent}"
            else:
                resolved_source_ref = "unspecified-source"

        # Confidence level assignment
        resolved_confidence = confidence
        if resolved_confidence is None:
            resolved_confidence = DEFAULT_CONFIDENCE_MAP.get(mem_type, 0.80)

        # 1. Allocate unique monotonic memory ID under dedicated id_sequence.lock
        id_gen = MemoryIdGenerator(p_dir)
        mem_id = id_gen.next_memory_id()

        target_dir_name = TYPE_TO_DIR.get(mem_type, "observations")
        target_dir = p_dir / target_dir_name
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"{mem_id}.md"

        if target_file.exists():
            raise EntityAlreadyExistsError(f"Memory file {target_file} already exists.")

        now = utc_now()
        fm = MemoryFrontmatter(
            id=mem_id,
            project_id=project_id,
            type=mem_type,
            title=title.strip(),
            created_at=now,
            updated_at=now,
            status=MemoryStatus.ACTIVE,
            source_type=resolved_source_type,
            source_agent=source_agent,
            source_skill=source_skill,
            source_ref=resolved_source_ref,
            confidence=resolved_confidence,
            tags=tags or [],
            related=related_memory_ids or [],
            supersedes=supersedes,
            superseded_by=superseded_by,
            experiment_id=experiment_id,
            paper_section=paper_section,
            metrics_summary=metrics_summary,
            parent_experiment=parent_experiment,
            artifact_paths=artifact_paths or [],
        )

        # Security: Sanitize markdown body to prevent secret / credential leaks
        clean_content = sanitize_markdown_text(content.strip())
        body_to_write = clean_content
        if not clean_content.startswith("# "):
            body_to_write = f"# {title.strip()}\n\n{clean_content}"

        full_text = dump_frontmatter(fm.model_dump(mode="json"), body_to_write)

        # 2. Fine-grained lock per memory file during atomic write
        mem_lock = p_dir / ".researchos" / f"{mem_id}.lock"
        with file_lock(mem_lock, timeout=10.0):
            atomic_write_text(target_file, full_text)

        # 3. Rebuild index (uses dedicated index.lock) and touch project
        self.project_svc.rebuild_index(project_id)
        self.project_svc.touch_project(project_id)

        rel_path = f"{target_dir_name}/{mem_id}.md"
        return Memory(frontmatter=fm, content=body_to_write, file_path=rel_path)

    def get_memory(self, project_id: str, memory_id: str) -> Memory:
        """Retrieves a memory record by ID."""
        mem_path = self._find_memory_path(project_id, memory_id)
        if not mem_path:
            raise MemoryNotFoundError(
                f"Memory '{memory_id}' not found in project '{project_id}'."
            )

        content = mem_path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(content)
        fm = MemoryFrontmatter.model_validate(meta)
        p_dir = self._get_project_dir(project_id)
        rel_path = mem_path.relative_to(p_dir).as_posix()
        return Memory(frontmatter=fm, content=body, file_path=rel_path)

    def update_memory(
        self,
        project_id: str,
        memory_id: str,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
        confidence: float | None = None,
        status: MemoryStatus | str | None = None,
        source_type: SourceType | str | None = None,
        source_ref: str | None = None,
        related_memory_ids: list[str] | None = None,
        allow_content_overwrite: bool = True,
        revision_note: str | None = None,
    ) -> Memory:
        """Safely updates attributes, metadata, or content of an existing memory."""
        mem_path = self._find_memory_path(project_id, memory_id)
        if not mem_path:
            raise MemoryNotFoundError(
                f"Memory '{memory_id}' not found in project '{project_id}'."
            )

        p_dir = self._get_project_dir(project_id)
        lock_path = p_dir / ".researchos" / f"{memory_id}.lock"

        with file_lock(lock_path, timeout=10.0):
            raw_text = mem_path.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(raw_text)
            fm = MemoryFrontmatter.model_validate(meta)

            # Prevent rewriting already superseded or archived records unless reactivating
            if fm.status in (MemoryStatus.SUPERSEDED, MemoryStatus.ARCHIVED):
                if content is not None and content.strip() != body.strip():
                    raise ValidationError(
                        f"Cannot overwrite content of {fm.status.value} memory '{memory_id}'. "
                        f"Create a new memory or use supersede_memory instead."
                    )

            if title is not None:
                fm.title = title.strip()
            if tags is not None:
                fm.tags = tags
            if confidence is not None:
                fm.confidence = confidence
            if source_type is not None:
                fm.source_type = source_type
            if source_ref is not None:
                fm.source_ref = source_ref
            if status is not None:
                if isinstance(status, str):
                    fm.status = MemoryStatus(status.lower().strip())
                else:
                    fm.status = status
            if related_memory_ids is not None:
                fm.related = related_memory_ids

            fm.updated_at = utc_now()

            # Process body update with sanitization
            new_body = body
            if content is not None:
                sanitized_content = sanitize_markdown_text(content.strip())
                if revision_note:
                    new_body = f"{sanitized_content}\n\n> [!NOTE] Revision ({fm.updated_at.strftime('%Y-%m-%d')})\n> {revision_note.strip()}"
                else:
                    new_body = sanitized_content

            new_text = dump_frontmatter(fm.model_dump(mode="json"), new_body)
            atomic_write_text(mem_path, new_text)

        self.project_svc.rebuild_index(project_id)
        self.project_svc.touch_project(project_id)

        rel_path = mem_path.relative_to(p_dir).as_posix()
        return Memory(frontmatter=fm, content=new_body, file_path=rel_path)

    def supersede_memory(
        self,
        project_id: str,
        old_memory_id: str,
        title: str,
        content: str,
        reason: str,
        type: MemoryType | str | None = None,
        tags: list[str] | None = None,
        source_type: SourceType | str | None = None,
        source_agent: str | None = None,
        source_skill: str | None = None,
        source_ref: str | None = None,
        confidence: float | None = None,
        related_memory_ids: list[str] | None = None,
    ) -> Memory:
        """Atomically supersedes an old memory with a new record.

        Guarantees:
          - Cycle detection: prevents A supersedes B, B supersedes A loops.
          - Transactional rollback: if creation of the new memory or writing fails,
            the old memory is restored to its exact previous state.
          - Bidirectional linking: new memory records `supersedes: old_id`,
            old memory records `superseded_by: new_id`.
          - Project-level lock protection against concurrent modifications.
        """
        p_dir = self._get_project_dir(project_id)
        old_path = self._find_memory_path(project_id, old_memory_id)
        if not old_path:
            raise MemoryNotFoundError(
                f"Old memory '{old_memory_id}' not found in project '{project_id}'."
            )

        if not reason or not reason.strip():
            raise ValidationError("A specific revision reason is required to supersede a memory.")

        # Project-level transaction lock
        lock_path = p_dir / ".researchos" / "project.lock"
        with file_lock(lock_path, timeout=10.0):
            # Backup original text for rollback
            old_raw_backup = old_path.read_text(encoding="utf-8")
            old_meta, old_body = parse_frontmatter(old_raw_backup)
            old_fm = MemoryFrontmatter.model_validate(old_meta)

            # Cycle detection: check if old_memory is already superseded or involved in a cycle
            if old_fm.supersedes and old_fm.supersedes == old_memory_id:
                raise ValidationError(f"Self-referential supersede detected on '{old_memory_id}'.")

            target_type = old_fm.type if type is None else (
                type if isinstance(type, MemoryType) else MemoryType(str(type).lower().strip())
            )

            # Build content citing revision reason
            clean_new_content = sanitize_markdown_text(content.strip())
            amended_content = (
                f"> [!NOTE] Supersedes `{old_memory_id}`\n"
                f"> **Reason**: {reason.strip()}\n\n"
                f"{clean_new_content}"
            )

            all_related = list(related_memory_ids or [])
            if old_memory_id not in all_related:
                all_related.append(old_memory_id)

            all_tags = list(tags) if tags is not None else list(old_fm.tags)
            if "revised" not in all_tags:
                all_tags.append("revised")

            new_target_file: Path | None = None
            try:
                # 1. Generate new memory ID
                id_gen = MemoryIdGenerator(p_dir)
                new_mem_id = id_gen.next_memory_id()

                target_dir_name = TYPE_TO_DIR.get(target_type, "observations")
                target_dir = p_dir / target_dir_name
                target_dir.mkdir(parents=True, exist_ok=True)
                new_target_file = target_dir / f"{new_mem_id}.md"

                now = utc_now()
                new_fm = MemoryFrontmatter(
                    id=new_mem_id,
                    project_id=project_id,
                    type=target_type,
                    title=title.strip(),
                    created_at=now,
                    updated_at=now,
                    status=MemoryStatus.ACTIVE,
                    source_type=source_type or old_fm.source_type,
                    source_agent=source_agent or old_fm.source_agent,
                    source_skill=source_skill or "memory-update",
                    source_ref=source_ref or old_fm.source_ref,
                    confidence=confidence if confidence is not None else old_fm.confidence,
                    tags=all_tags,
                    related=all_related,
                    supersedes=old_memory_id,
                    superseded_by=None,
                )

                body_to_write = amended_content
                if not amended_content.startswith("# "):
                    body_to_write = f"# {title.strip()}\n\n{amended_content}"

                new_full_text = dump_frontmatter(new_fm.model_dump(mode="json"), body_to_write)
                atomic_write_text(new_target_file, new_full_text)

                # 2. Update old memory with superseded status and pointer to new memory
                old_fm.status = MemoryStatus.SUPERSEDED
                old_fm.superseded_by = new_mem_id
                old_fm.updated_at = now

                old_updated_text = dump_frontmatter(old_fm.model_dump(mode="json"), old_body)
                atomic_write_text(old_path, old_updated_text)

                # 3. Synchronize project indexes
                self.project_svc.rebuild_index(project_id)
                self.project_svc.touch_project(project_id)

                rel_path = f"{target_dir_name}/{new_mem_id}.md"
                return Memory(frontmatter=new_fm, content=body_to_write, file_path=rel_path)

            except Exception:
                # Rollback transaction on any error
                try:
                    atomic_write_text(old_path, old_raw_backup)
                except Exception:
                    pass
                if new_target_file and new_target_file.exists():
                    try:
                        new_target_file.unlink()
                    except OSError:
                        pass
                raise

    def archive_memory(self, project_id: str, memory_id: str, reason: str | None = None) -> Memory:
        """Moves a memory to archive/ and updates its status to archived."""
        mem_path = self._find_memory_path(project_id, memory_id)
        if not mem_path:
            raise MemoryNotFoundError(
                f"Memory '{memory_id}' not found in project '{project_id}'."
            )

        p_dir = self._get_project_dir(project_id)
        archive_dir = p_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        dest_file = archive_dir / mem_path.name

        raw_text = mem_path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(raw_text)
        meta["status"] = MemoryStatus.ARCHIVED.value
        meta["updated_at"] = utc_now().isoformat()

        if reason:
            body = f"> [!NOTE] Archived\n> **Reason**: {reason.strip()}\n\n{body}"

        updated_text = dump_frontmatter(meta, body)
        atomic_write_text(dest_file, updated_text)

        # Remove original file if it was outside archive
        if mem_path.resolve() != dest_file.resolve() and mem_path.exists():
            mem_path.unlink()

        self.project_svc.rebuild_index(project_id)
        self.project_svc.touch_project(project_id)

        fm = MemoryFrontmatter.model_validate(meta)
        return Memory(frontmatter=fm, content=body, file_path=f"archive/{dest_file.name}")
