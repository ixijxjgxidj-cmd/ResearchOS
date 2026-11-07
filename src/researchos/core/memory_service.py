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
    utc_now,
)
from researchos.utils.exceptions import (
    EntityAlreadyExistsError,
    MemoryNotFoundError,
    ProjectNotFoundError,
    ValidationError,
)
from researchos.utils.ids import MemoryIdGenerator


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
        source_agent: str | None = None,
        source_skill: str | None = None,
        source_ref: str | None = None,
        related_memory_ids: list[str] | None = None,
        confidence: float | None = None,
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

        # Generate unique memory ID
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
            source_agent=source_agent,
            source_skill=source_skill,
            source_ref=source_ref,
            confidence=confidence,
            tags=tags or [],
            related=related_memory_ids or [],
            supersedes=None,
        )

        # Standard header in body if not already present
        clean_content = content.strip()
        body_to_write = clean_content
        if not clean_content.startswith("# "):
            body_to_write = f"# {title.strip()}\n\n{clean_content}"

        full_text = dump_frontmatter(fm.model_dump(mode="json"), body_to_write)

        lock_path = p_dir / ".researchos" / f"{mem_id}.lock"
        with file_lock(lock_path, timeout=10.0):
            atomic_write_text(target_file, full_text)

        # Rebuild index and touch project
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
        related_memory_ids: list[str] | None = None,
    ) -> Memory:
        """Safely updates attributes or content of an existing memory."""
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

            if title is not None:
                fm.title = title.strip()
            if tags is not None:
                fm.tags = tags
            if confidence is not None:
                fm.confidence = confidence
            if status is not None:
                if isinstance(status, str):
                    fm.status = MemoryStatus(status.lower().strip())
                else:
                    fm.status = status
            if related_memory_ids is not None:
                fm.related = related_memory_ids

            fm.updated_at = utc_now()
            new_body = content.strip() if content is not None else body

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
        source_agent: str | None = None,
        source_skill: str | None = None,
        source_ref: str | None = None,
        confidence: float | None = None,
        related_memory_ids: list[str] | None = None,
    ) -> Memory:
        """Supersedes an old memory with a new memory record, linking them explicitly."""
        old_mem = self.get_memory(project_id, old_memory_id)

        # 1. Update old memory status to superseded
        self.update_memory(project_id, old_memory_id, status=MemoryStatus.SUPERSEDED)

        # 2. Determine new type
        target_type = old_mem.type if type is None else type

        # 3. Create new memory with supersedes link and reason
        amended_content = (
            f"> [!NOTE] Supersedes `{old_memory_id}`\n"
            f"> **Reason**: {reason.strip()}\n\n"
            f"{content.strip()}"
        )

        all_related = list(related_memory_ids or [])
        if old_memory_id not in all_related:
            all_related.append(old_memory_id)

        all_tags = list(tags) if tags is not None else list(old_mem.tags)
        if "revised" not in all_tags:
            all_tags.append("revised")

        # Create new memory
        new_mem = self.add_memory(
            project_id=project_id,
            type=target_type,
            title=title,
            content=amended_content,
            tags=all_tags,
            source_agent=source_agent,
            source_skill=source_skill,
            source_ref=source_ref,
            related_memory_ids=all_related,
            confidence=confidence,
        )

        # Update new memory frontmatter to set supersedes
        new_path = self._find_memory_path(project_id, new_mem.id)
        if new_path:
            raw_text = new_path.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(raw_text)
            meta["supersedes"] = old_memory_id
            new_text = dump_frontmatter(meta, body)
            atomic_write_text(new_path, new_text)

        self.project_svc.rebuild_index(project_id)
        return self.get_memory(project_id, new_mem.id)

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
