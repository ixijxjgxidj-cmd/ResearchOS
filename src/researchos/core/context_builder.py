"""Context Builder service for re-hydrating Agent memory within strict token budgets."""

import math
from pathlib import Path

from pydantic import BaseModel, Field

from researchos.core.project_service import SUBDIRS, ProjectService
from researchos.core.retrieval_service import RetrievalService
from researchos.core.storage_service import parse_frontmatter
from researchos.models.memory import (
    Memory,
    MemoryFrontmatter,
    MemoryStatus,
    MemoryType,
)
from researchos.utils.exceptions import ProjectNotFoundError, ValidationError


def estimate_tokens(text: str) -> int:
    """Estimates token count conservatively across mixed Latin/CJK/Code text.

    Heuristics:
      - CJK characters: ~1.8 tokens per character.
      - Latin / alphanumeric characters: ~1 token per 3.5 characters (~1.3 tokens per word).
      - Whitespace and punctuation: counted conservatively.
    """
    if not text:
        return 0

    cjk_count = 0
    non_cjk_count = 0

    for ch in text:
        if "\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf":
            cjk_count += 1
        elif not ch.isspace():
            non_cjk_count += 1

    tokens = int(cjk_count * 1.8 + math.ceil(non_cjk_count / 3.5))
    return max(1, tokens)


class ContextChunk:
    """A prioritized context chunk tagged with its authoritative source file."""

    def __init__(
        self,
        priority: int,
        source_file: str,
        title: str,
        text: str,
        memory_id: str | None = None,
    ) -> None:
        self.priority = priority  # 1 (highest) to 8 (lowest)
        self.source_file = source_file
        self.title = title
        self.text = text
        self.memory_id = memory_id
        self.tokens = estimate_tokens(self.rendered())

    def rendered(self) -> str:
        return f"### {self.title}\n> **Source**: `{self.source_file}`\n\n{self.text.strip()}\n"


class ContextMetadata(BaseModel):
    """Diagnostic metadata for a built context pack."""

    project_id: str
    context_mode: str
    task: str | None = None
    max_tokens: int
    used_tokens: int
    total_available_tokens: int
    included_chunks_count: int
    omitted_count: int
    omitted_ids: list[str] = Field(default_factory=list)
    truncated_files: list[str] = Field(default_factory=list)


class ContextBuilder:
    """Builds deterministic, token-budgeted context packs for research agents."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.project_svc = ProjectService(self.vault_root)
        self.retrieval_svc = RetrievalService(self.vault_root)

    def build_context(
        self,
        project_id: str,
        task: str | None = None,
        context_mode: str = "quick",
        max_tokens: int = 4000,
        include_history: bool = False,
    ) -> str:
        """Constructs a deterministic context pack respecting max_tokens budget (string output)."""
        pack, _ = self.build_context_pack(
            project_id=project_id,
            task=task,
            context_mode=context_mode,
            max_tokens=max_tokens,
            include_history=include_history,
        )
        return pack

    def build_context_pack(
        self,
        project_id: str,
        task: str | None = None,
        context_mode: str = "quick",
        max_tokens: int = 4000,
        include_history: bool = False,
    ) -> tuple[str, ContextMetadata]:
        """Constructs a context pack and returns (rendered_markdown, diagnostic_metadata).

        Modes:
            - 'quick': PROJECT.md, STATE.md core, HANDOFF.md, top key active memories (<= 5).
            - 'task': Quick Context + BM25 & relation-retrieved active memories for the task.
            - 'full': Comprehensive project context + all active memories + (optional) segregated history.
        """
        p_dir = self.project_svc.get_project_dir(project_id)
        if not (p_dir / "PROJECT.md").exists():
            raise ProjectNotFoundError(f"Project '{project_id}' does not exist.")

        mode = context_mode.lower().strip()
        if mode not in ("quick", "task", "full"):
            raise ValidationError(
                f"Invalid context_mode '{context_mode}'. Allowed: 'quick', 'task', 'full'."
            )

        chunks: list[ContextChunk] = []

        # 1. Always-on Project Memory (Priority 1)
        mem_file = p_dir / "MEMORY.md"
        if mem_file.exists():
            mem_text = mem_file.read_text(encoding="utf-8")
            chunks.append(ContextChunk(1, f"{project_id}/MEMORY.md", "Always-on Project Memory", mem_text))

        # 2. Project Basic Info (Priority 2)
        proj_file = p_dir / "PROJECT.md"
        if proj_file.exists():
            proj_text = proj_file.read_text(encoding="utf-8")
            _, body = parse_frontmatter(proj_text)
            chunks.append(ContextChunk(2, f"{project_id}/PROJECT.md", "Project Overview", body))

        # 3. Current State (Priority 3)
        state_file = p_dir / "STATE.md"
        if state_file.exists():
            state_text = state_file.read_text(encoding="utf-8")
            chunks.append(ContextChunk(3, f"{project_id}/STATE.md", "Current Research State", state_text))

        # 4. Current Handoff (Priority 4)
        handoff_file = p_dir / "HANDOFF.md"
        if handoff_file.exists():
            handoff_text = handoff_file.read_text(encoding="utf-8")
            chunks.append(ContextChunk(4, f"{project_id}/HANDOFF.md", "Latest Agent Handoff", handoff_text))

        # 5. Load memories from project
        all_memories = self._load_all_memories(project_id)

        # Strict filter: ONLY active memories are considered for core active facts
        active_memories = [m for m in all_memories if m.status == MemoryStatus.ACTIVE]
        superseded_memories = [m for m in all_memories if m.status == MemoryStatus.SUPERSEDED]
        archived_memories = [m for m in all_memories if m.status == MemoryStatus.ARCHIVED]

        # Priority 5: Negative Knowledge (Essential pitfalls to never repeat)
        negatives = [m for m in active_memories if m.type == MemoryType.NEGATIVE]
        for neg in negatives:
            chunks.append(
                ContextChunk(
                    5,
                    f"{project_id}/{neg.file_path}",
                    f"Negative Knowledge (Pitfall): {neg.title}",
                    neg.content,
                    memory_id=neg.id,
                )
            )

        # Priority 6: Architectural / Scientific Decisions
        decisions = [m for m in active_memories if m.type == MemoryType.DECISION]
        dec_candidates = decisions[-3:] if mode == "quick" else decisions
        for dec in dec_candidates:
            chunks.append(
                ContextChunk(
                    6,
                    f"{project_id}/{dec.file_path}",
                    f"Decision: {dec.title}",
                    dec.content,
                    memory_id=dec.id,
                )
            )

        # Priority 7: Task-relevant memories (in 'task' mode)
        if mode == "task" and task:
            hits = self.retrieval_svc.search_memories(
                project_id=project_id,
                query=task,
                status=MemoryStatus.ACTIVE,
                limit=10,
            )
            already_included_ids = {c.memory_id for c in chunks if c.memory_id}
            for hit in hits:
                if hit.memory_id not in already_included_ids:
                    target_mem = next((m for m in active_memories if m.id == hit.memory_id), None)
                    if target_mem:
                        chunks.append(
                            ContextChunk(
                                7,
                                f"{project_id}/{target_mem.file_path}",
                                f"Task Relevant ({target_mem.type.value}): {target_mem.title}",
                                target_mem.content,
                                memory_id=target_mem.id,
                            )
                        )
                        already_included_ids.add(target_mem.id)

        # Priority 8: Open Hypotheses
        hypotheses = [m for m in active_memories if m.type == MemoryType.HYPOTHESIS]
        hypo_candidates = hypotheses[-3:] if mode == "quick" else hypotheses
        for hyp in hypo_candidates:
            chunks.append(
                ContextChunk(
                    8,
                    f"{project_id}/{hyp.file_path}",
                    f"Hypothesis: {hyp.title}",
                    hyp.content,
                    memory_id=hyp.id,
                )
            )

        # Priority 9: Empirical Observations, Knowledge, References
        if mode == "full":
            other_types = [
                m
                for m in active_memories
                if m.type in (MemoryType.OBSERVATION, MemoryType.KNOWLEDGE, MemoryType.REFERENCE)
            ]
            already_included_ids = {c.memory_id for c in chunks if c.memory_id}
            for oth in other_types:
                if oth.id not in already_included_ids:
                    chunks.append(
                        ContextChunk(
                            9,
                            f"{project_id}/{oth.file_path}",
                            f"{oth.type.value.capitalize()}: {oth.title}",
                            oth.content,
                            memory_id=oth.id,
                        )
                    )
                    already_included_ids.add(oth.id)
        else:
            # In quick or task mode, include up to 5 recent active observations
            recent_obs = [m for m in active_memories if m.type == MemoryType.OBSERVATION][-5:]
            already_included_ids = {c.memory_id for c in chunks if c.memory_id}
            for obs in recent_obs:
                if obs.id not in already_included_ids:
                    chunks.append(
                        ContextChunk(
                            9,
                            f"{project_id}/{obs.file_path}",
                            f"Observation: {obs.title}",
                            obs.content,
                            memory_id=obs.id,
                        )
                    )
                    already_included_ids.add(obs.id)

        # Deduplicate chunks by source_file
        unique_chunks: list[ContextChunk] = []
        seen_sources: set[str] = set()
        for c in chunks:
            if c.source_file not in seen_sources:
                seen_sources.add(c.source_file)
                unique_chunks.append(c)

        # Sort chunks strictly by priority (1 to 8)
        unique_chunks.sort(key=lambda x: x.priority)

        # Build context header
        header = (
            f"# ResearchOS Context Pack\n"
            f"- **Project ID**: `{project_id}`\n"
            f"- **Context Mode**: `{mode}`\n"
            f"- **Task Focus**: {task or 'General'}\n"
            f"- **Budget (max_tokens)**: `{max_tokens}`\n\n"
            f"> [!IMPORTANT]\n"
            f"> This context pack is a transient view compiled from authoritative Markdown memory files.\n"
            f"> Each block cites its original file path.\n\n"
            f"---\n\n"
        )

        current_tokens = estimate_tokens(header)
        assembled_chunks: list[str] = []
        omitted_ids: list[str] = []
        truncated_files: list[str] = []
        omitted_count = 0
        total_available_tokens = current_tokens + sum(c.tokens for c in unique_chunks)

        for chunk in unique_chunks:
            if current_tokens + chunk.tokens <= max_tokens:
                assembled_chunks.append(chunk.rendered())
                current_tokens += chunk.tokens
            else:
                # If high-priority chunk (priority <= 4), attempt truncation
                remaining = max_tokens - current_tokens
                if chunk.priority <= 4 and remaining > 80:
                    allowed_chars = int(remaining * 2.8)
                    truncated_text = (
                        chunk.text[:allowed_chars]
                        + f"\n\n... *(truncated to fit token budget; see `{chunk.source_file}`)*"
                    )
                    temp_chunk = ContextChunk(
                        chunk.priority, chunk.source_file, chunk.title, truncated_text
                    )
                    assembled_chunks.append(temp_chunk.rendered())
                    current_tokens += temp_chunk.tokens
                    truncated_files.append(chunk.source_file)
                else:
                    omitted_count += 1
                    if chunk.memory_id:
                        omitted_ids.append(chunk.memory_id)

        # If full mode and include_history is explicitly enabled, add segregated section
        if mode == "full" and include_history and (superseded_memories or archived_memories):
            hist_header = (
                "\n\n---\n\n"
                "## Historical / Deprecated Records\n\n"
                "> [!WARNING]\n"
                "> The following memories have been SUPERSEDED or ARCHIVED. "
                "They are provided strictly for historical audit and MUST NOT be cited as active facts.\n\n"
            )
            hist_tokens = estimate_tokens(hist_header)
            if current_tokens + hist_tokens < max_tokens:
                assembled_chunks.append(hist_header)
                current_tokens += hist_tokens
                for old in (superseded_memories + archived_memories)[:5]:
                    old_chunk = ContextChunk(
                        9,
                        f"{project_id}/{old.file_path}",
                        f"[{old.status.value.upper()}] {old.title}",
                        old.content,
                        memory_id=old.id,
                    )
                    if current_tokens + old_chunk.tokens <= max_tokens:
                        assembled_chunks.append(old_chunk.rendered())
                        current_tokens += old_chunk.tokens

        if omitted_count > 0:
            assembled_chunks.append(
                f"\n> [!NOTE]\n"
                f"> *{omitted_count} lower-priority memory items were omitted to respect the {max_tokens} token budget. "
                f"Omitted IDs: {', '.join(omitted_ids[:10]) if omitted_ids else 'None'}*"
            )

        metadata = ContextMetadata(
            project_id=project_id,
            context_mode=mode,
            task=task,
            max_tokens=max_tokens,
            used_tokens=current_tokens,
            total_available_tokens=total_available_tokens,
            included_chunks_count=len(assembled_chunks),
            omitted_count=omitted_count,
            omitted_ids=omitted_ids,
            truncated_files=truncated_files,
        )

        return header + "\n".join(assembled_chunks), metadata

    def _load_all_memories(self, project_id: str) -> list[Memory]:
        p_dir = self.project_svc.get_project_dir(project_id)
        memories: list[Memory] = []
        for sub in SUBDIRS:
            sub_dir = p_dir / sub
            if not sub_dir.exists():
                continue
            for f in sorted(sub_dir.glob("*.md")):
                try:
                    content = f.read_text(encoding="utf-8")
                    meta, body = parse_frontmatter(content)
                    if "id" in meta and "type" in meta:
                        fm = MemoryFrontmatter.model_validate(meta)
                        rel_path = f.relative_to(p_dir).as_posix()
                        memories.append(Memory(frontmatter=fm, content=body, file_path=rel_path))
                except Exception:
                    continue
        return memories
