"""Context Builder service for re-hydrating Agent memory within strict token budgets.

Implements Three-Level Memory Retrieval:
    L0 — Quick Memory: MEMORY.md (400-800 tokens, auto-loaded)
    L1 — Context Memory: PROJECT.md, STATE.md, HANDOFF.md, INDEX.md
    L2 — Detailed Memory: records/ (on-demand empirical evidence and knowledge)

Modes:
    - 'quick': Strictly L0 (MEMORY.md) for ultra-fast post-compaction recovery.
    - 'task': L0 + BM25-retrieved L1/L2 memories relevant to the immediate task.
    - 'paper': L0 + structured experimental evidence preserving Run ID, metrics, and verification status.
    - 'full': Comprehensive project context pack for complete auditing and export.
"""

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
        self.priority = priority  # 1 (highest) to 9 (lowest)
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
        paper_section: str | None = None,
    ) -> str:
        """Constructs a deterministic context pack respecting max_tokens budget (string output)."""
        pack, _ = self.build_context_pack(
            project_id=project_id,
            task=task,
            context_mode=context_mode,
            max_tokens=max_tokens,
            include_history=include_history,
            paper_section=paper_section,
        )
        return pack

    def build_context_pack(
        self,
        project_id: str,
        task: str | None = None,
        context_mode: str = "quick",
        max_tokens: int = 4000,
        include_history: bool = False,
        paper_section: str | None = None,
    ) -> tuple[str, ContextMetadata]:
        """Constructs a context pack and returns (rendered_markdown, diagnostic_metadata).

        Modes:
            - 'quick': L0 only (MEMORY.md). Ultra-lean snapshot (400-800 tokens).
            - 'task': L0 (MEMORY.md) + BM25 task-relevant L1/L2 records up to max_tokens.
            - 'paper': L0 (MEMORY.md) + structured experimental evidence matching section/query.
            - 'full': Comprehensive project context + all active memories + history.
        """
        p_dir = self.project_svc.get_project_dir(project_id)
        if not (p_dir / "PROJECT.md").exists():
            raise ProjectNotFoundError(f"Project '{project_id}' does not exist.")

        mode = context_mode.lower().strip()
        if mode not in ("quick", "task", "paper", "full"):
            raise ValidationError(
                f"Invalid context_mode '{context_mode}'. Allowed: 'quick', 'task', 'paper', 'full'."
            )

        chunks: list[ContextChunk] = []

        # 1. L0: Always-on Project Memory (Priority 1)
        mem_file = p_dir / "MEMORY.md"
        if not mem_file.exists():
            from researchos.core.project_memory_service import ProjectMemoryService
            pms = ProjectMemoryService(self.vault_root)
            pms.rebuild_project_memory(project_id)

        mem_text = mem_file.read_text(encoding="utf-8")
        chunks.append(ContextChunk(1, f"{project_id}/MEMORY.md", "Always-on Project Memory", mem_text))

        # Load all memories for filtering and omission diagnostics
        all_memories = self._load_all_memories(project_id)
        active_memories = [
            m for m in all_memories
            if (m.status == MemoryStatus.ACTIVE or getattr(m.status, "value", str(m.status)) in ("active", "verified"))
        ]

        if mode == "quick":
            # Quick mode: strictly L0. All other detailed active memories are omitted by design.
            pass

        elif mode == "task":
            # Task mode: L0 + L1 context files + BM25 searched L2 memories
            proj_file = p_dir / "PROJECT.md"
            if proj_file.exists():
                _, body = parse_frontmatter(proj_file.read_text(encoding="utf-8"))
                chunks.append(ContextChunk(2, f"{project_id}/PROJECT.md", "Project Overview", body))

            state_file = p_dir / "STATE.md"
            if state_file.exists():
                chunks.append(ContextChunk(3, f"{project_id}/STATE.md", "Current Research State", state_file.read_text(encoding="utf-8")))

            handoff_file = p_dir / "HANDOFF.md"
            if handoff_file.exists():
                chunks.append(ContextChunk(4, f"{project_id}/HANDOFF.md", "Latest Agent Handoff", handoff_file.read_text(encoding="utf-8")))

            # BM25 Task-relevant search
            search_query = task or "research status"
            hits = self.retrieval_svc.search_memories(
                project_id=project_id,
                query=search_query,
                status=MemoryStatus.ACTIVE,
                limit=10,
            )
            already_included_ids = {c.memory_id for c in chunks if c.memory_id}
            for hit in hits:
                if hit.memory_id not in already_included_ids:
                    target_mem = next((m for m in active_memories if m.id == hit.memory_id), None)
                    if target_mem:
                        t_val = getattr(target_mem.type, "value", str(target_mem.type))
                        chunks.append(
                            ContextChunk(
                                5,
                                f"{project_id}/{target_mem.file_path}",
                                f"Task Relevant ({t_val}): {target_mem.title}",
                                target_mem.content,
                                memory_id=target_mem.id,
                            )
                        )
                        already_included_ids.add(target_mem.id)

            # Key Decisions and Pitfalls
            for dec in [m for m in active_memories if m.type == MemoryType.DECISION][-3:]:
                if dec.id not in already_included_ids:
                    chunks.append(ContextChunk(6, f"{project_id}/{dec.file_path}", f"Decision: {dec.title}", dec.content, memory_id=dec.id))
                    already_included_ids.add(dec.id)

            for neg in [m for m in active_memories if m.type == MemoryType.NEGATIVE][-3:]:
                if neg.id not in already_included_ids:
                    chunks.append(ContextChunk(7, f"{project_id}/{neg.file_path}", f"Negative Pitfall: {neg.title}", neg.content, memory_id=neg.id))
                    already_included_ids.add(neg.id)

        elif mode == "paper":
            # Paper mode: L0 + Paper Evidence Inventory & targeted section findings
            from researchos.core.paper_service import PaperService
            paper_svc = PaperService(self.vault_root)
            inv = paper_svc.get_paper_inventory(project_id, paper_section=paper_section)

            for item in inv[:15]:
                mem = next((m for m in all_memories if m.id == item.memory_id), None)
                if not mem:
                    continue

                t_val = getattr(mem.type, "value", str(mem.type))
                exp_id = mem.frontmatter.experiment_id or item.experiment_id or "N/A"
                source_ref = mem.frontmatter.source_ref or "N/A"
                if isinstance(source_ref, list):
                    source_ref = ", ".join(source_ref)

                status_label = item.status
                is_hypo = mem.type == MemoryType.HYPOTHESIS
                disclaimer = "\n> [!NOTE]\n> **Status**: [Hypothesis - Unverified Claim; Not Established Empirical Finding]\n" if is_hypo else ""

                evidence_text = (
                    f"> **Evidence ID**: `{mem.id}` | **Type**: `{t_val}`\n"
                    f"> **Experiment ID**: `{exp_id}` | **Run / Provenance**: `{source_ref}`\n"
                    f"> **Section**: `{item.paper_section or 'Unassigned'}` | **Status**: `{status_label}`\n"
                    f"> **Metrics**: {item.metrics_summary or 'None specified'}\n"
                    f"{disclaimer}\n"
                    f"{mem.content}\n"
                )
                chunks.append(
                    ContextChunk(
                        5,
                        f"{project_id}/{mem.file_path}",
                        f"Paper Evidence: {mem.title}",
                        evidence_text,
                        memory_id=mem.id,
                    )
                )

        elif mode == "full":
            # Full mode: Comprehensive inspection
            proj_file = p_dir / "PROJECT.md"
            if proj_file.exists():
                _, body = parse_frontmatter(proj_file.read_text(encoding="utf-8"))
                chunks.append(ContextChunk(2, f"{project_id}/PROJECT.md", "Project Overview", body))

            state_file = p_dir / "STATE.md"
            if state_file.exists():
                chunks.append(ContextChunk(3, f"{project_id}/STATE.md", "Current Research State", state_file.read_text(encoding="utf-8")))

            handoff_file = p_dir / "HANDOFF.md"
            if handoff_file.exists():
                chunks.append(ContextChunk(4, f"{project_id}/HANDOFF.md", "Latest Agent Handoff", handoff_file.read_text(encoding="utf-8")))

            for mem in active_memories:
                t_val = getattr(mem.type, "value", str(mem.type))
                chunks.append(
                    ContextChunk(
                        6,
                        f"{project_id}/{mem.file_path}",
                        f"{t_val.capitalize()}: {mem.title}",
                        mem.content,
                        memory_id=mem.id,
                    )
                )

        # Deduplicate chunks by source_file
        unique_chunks: list[ContextChunk] = []
        seen_sources: set[str] = set()
        for c in chunks:
            if c.source_file not in seen_sources:
                seen_sources.add(c.source_file)
                unique_chunks.append(c)

        # Sort chunks strictly by priority
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
        total_available_tokens = current_tokens + sum(c.tokens for c in unique_chunks)

        for chunk in unique_chunks:
            if current_tokens + chunk.tokens <= max_tokens:
                assembled_chunks.append(chunk.rendered())
                current_tokens += chunk.tokens
            else:
                # Omit chunk to respect budget
                if chunk.memory_id:
                    omitted_ids.append(chunk.memory_id)
                truncated_files.append(chunk.source_file)

        # If in quick mode or task mode, calculate how many detailed active memories were omitted
        included_mids = {c.memory_id for c in unique_chunks if c.memory_id and c.source_file not in truncated_files}
        for am in active_memories:
            if am.id not in included_mids and am.id not in omitted_ids:
                omitted_ids.append(am.id)

        omitted_count = len(omitted_ids)

        # Append budget diagnostic note if items were omitted
        footer = ""
        if omitted_count > 0:
            footer = (
                f"\n---\n"
                f"> [!NOTE]\n"
                f"> Context pack limited to {current_tokens} tokens. "
                f"{omitted_count} memories omitted to respect token budget.\n"
            )

        full_rendered = header + "\n".join(assembled_chunks) + footer

        metadata = ContextMetadata(
            project_id=project_id,
            context_mode=mode,
            task=task,
            max_tokens=max_tokens,
            used_tokens=estimate_tokens(full_rendered),
            total_available_tokens=total_available_tokens,
            included_chunks_count=len(assembled_chunks),
            omitted_count=omitted_count,
            omitted_ids=omitted_ids,
            truncated_files=truncated_files,
        )

        return full_rendered, metadata

    def _load_all_memories(self, project_id: str) -> list[Memory]:
        p_dir = self.project_svc.get_project_dir(project_id)
        memories = []
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
