"""Context Builder service for re-hydrating Agent memory within strict token budgets."""

import math
from pathlib import Path

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
    """Estimates token count conservatively across mixed Latin/CJK text."""
    if not text:
        return 0
    # Conservative estimate: ~3.2 characters per token on average
    return max(1, math.ceil(len(text) / 3.2))


class ContextChunk:
    """A prioritized context item tagged with its authoritative source file."""

    def __init__(self, priority: int, source_file: str, title: str, text: str) -> None:
        self.priority = priority  # 1 (highest) to 8 (lowest)
        self.source_file = source_file
        self.title = title
        self.text = text
        self.tokens = estimate_tokens(self.rendered())

    def rendered(self) -> str:
        return f"### {self.title}\n> **Source**: `{self.source_file}`\n\n{self.text.strip()}\n"


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
    ) -> str:
        """Constructs a deterministic context pack respecting max_tokens budget.

        Modes:
            - 'quick': PROJECT.md, STATE.md, INDEX summary, HANDOFF.md, top key memories.
            - 'task': Quick Context + memories relevant to the specified task.
            - 'full': Comprehensive project background, memories, decisions, and history.
        """
        p_dir = self.project_svc.get_project_dir(project_id)
        if not (p_dir / "PROJECT.md").exists():
            raise ProjectNotFoundError(f"Project '{project_id}' does not exist.")

        mode = context_mode.lower().strip()
        if mode not in ("quick", "task", "full"):
            raise ValidationError(f"Invalid context_mode '{context_mode}'. Allowed: 'quick', 'task', 'full'.")

        chunks: list[ContextChunk] = []

        # 1. Project Basic Info (Priority 1)
        proj_file = p_dir / "PROJECT.md"
        if proj_file.exists():
            proj_text = proj_file.read_text(encoding="utf-8")
            _, body = parse_frontmatter(proj_text)
            chunks.append(ContextChunk(1, f"{project_id}/PROJECT.md", "Project Overview", body))

        # 2. Current State (Priority 2)
        state_file = p_dir / "STATE.md"
        if state_file.exists():
            state_text = state_file.read_text(encoding="utf-8")
            chunks.append(ContextChunk(2, f"{project_id}/STATE.md", "Current Research State", state_text))

        # 3. Current Handoff (Priority 3)
        handoff_file = p_dir / "HANDOFF.md"
        if handoff_file.exists():
            handoff_text = handoff_file.read_text(encoding="utf-8")
            chunks.append(ContextChunk(3, f"{project_id}/HANDOFF.md", "Latest Agent Handoff", handoff_text))

        # 4. Load memories from project
        all_memories = self._load_all_memories(project_id)

        # Negative memories (Priority 6) - Essential pitfalls
        negatives = [m for m in all_memories if m.type == MemoryType.NEGATIVE and m.status == MemoryStatus.ACTIVE]
        for neg in negatives:
            chunks.append(
                ContextChunk(
                    6,
                    f"{project_id}/{neg.file_path}",
                    f"Negative Knowledge: {neg.title}",
                    neg.content,
                )
            )

        # Unresolved decisions (Priority 5)
        decisions = [m for m in all_memories if m.type == MemoryType.DECISION and m.status == MemoryStatus.ACTIVE]
        for dec in decisions[-5:]:  # Recent decisions
            chunks.append(
                ContextChunk(
                    5,
                    f"{project_id}/{dec.file_path}",
                    f"Decision: {dec.title}",
                    dec.content,
                )
            )

        # Task-related memories (Priority 4)
        if mode == "task" and task:
            hits = self.retrieval_svc.search_memories(project_id=project_id, query=task, limit=10)
            seen_ids = {neg.id for neg in negatives}.union({dec.id for dec in decisions})
            for hit in hits:
                if hit.memory_id not in seen_ids:
                    target_mem = next((m for m in all_memories if m.id == hit.memory_id), None)
                    if target_mem and target_mem.status == MemoryStatus.ACTIVE:
                        chunks.append(
                            ContextChunk(
                                4,
                                f"{project_id}/{target_mem.file_path}",
                                f"Task Relevant ({target_mem.type.value}): {target_mem.title}",
                                target_mem.content,
                            )
                        )
                        seen_ids.add(target_mem.id)

        # Recent Observations (Priority 7)
        observations = [m for m in all_memories if m.type == MemoryType.OBSERVATION and m.status == MemoryStatus.ACTIVE]
        for obs in observations[-5:]:
            chunks.append(
                ContextChunk(
                    7,
                    f"{project_id}/{obs.file_path}",
                    f"Observation: {obs.title}",
                    obs.content,
                )
            )

        # If Full context mode, load knowledge, hypotheses, references (Priority 8)
        if mode == "full":
            other_types = [m for m in all_memories if m.type in (MemoryType.KNOWLEDGE, MemoryType.HYPOTHESIS, MemoryType.REFERENCE)]
            for oth in other_types:
                chunks.append(
                    ContextChunk(
                        8,
                        f"{project_id}/{oth.file_path}",
                        f"{oth.type.value.capitalize()}: {oth.title}",
                        oth.content,
                    )
                )

        # Deduplicate chunks by source_file
        unique_chunks: list[ContextChunk] = []
        seen_sources: set[str] = set()
        for c in chunks:
            if c.source_file not in seen_sources:
                seen_sources.add(c.source_file)
                unique_chunks.append(c)

        # Sort chunks strictly by priority (1 to 8), then by descending creation if comparable
        unique_chunks.sort(key=lambda x: x.priority)

        # Assemble and enforce token budget
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
        omitted_count = 0

        for chunk in unique_chunks:
            if current_tokens + chunk.tokens <= max_tokens:
                assembled_chunks.append(chunk.rendered())
                current_tokens += chunk.tokens
            else:
                # If chunk is high priority (priority <= 3), attempt truncation to fit remainder
                remaining = max_tokens - current_tokens
                if chunk.priority <= 3 and remaining > 80:
                    allowed_chars = int(remaining * 2.8)
                    truncated_text = chunk.text[:allowed_chars] + f"\n\n... *(truncated to fit token budget; see `{chunk.source_file}`)*"
                    temp_chunk = ContextChunk(chunk.priority, chunk.source_file, chunk.title, truncated_text)
                    assembled_chunks.append(temp_chunk.rendered())
                    current_tokens += temp_chunk.tokens
                else:
                    omitted_count += 1

        if omitted_count > 0:
            assembled_chunks.append(
                f"\n> [!NOTE]\n> *{omitted_count} lower-priority memory items were omitted to respect the {max_tokens} token budget.*"
            )

        return header + "\n".join(assembled_chunks)

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
