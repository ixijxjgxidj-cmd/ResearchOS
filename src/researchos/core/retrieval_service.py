"""Memory retrieval and search service with strict project isolation."""

import re
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from researchos.core.project_service import SUBDIRS, ProjectService
from researchos.core.storage_service import parse_frontmatter
from researchos.models.memory import (
    MemoryFrontmatter,
    MemoryStatus,
    MemoryType,
)
from researchos.utils.exceptions import ProjectNotFoundError, ValidationError


class SearchHit(BaseModel):
    """Structured representation of a memory search result."""

    memory_id: str
    project_id: str
    type: str
    title: str
    snippet: str
    file_path: str
    created_at: str
    score: float
    relevance_reasons: list[str] = Field(default_factory=list)


class RetrievalService:
    """Performs isolated in-project searches and multi-criteria metadata filtering."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.project_svc = ProjectService(self.vault_root)

    def search_memories(
        self,
        project_id: str,
        query: str | None = None,
        type: MemoryType | str | None = None,
        tags: list[str] | None = None,
        status: MemoryStatus | str | None = None,
        time_start: datetime | str | None = None,
        time_end: datetime | str | None = None,
        limit: int = 20,
        cross_project: bool = False,
    ) -> list[SearchHit]:
        """Searches memories within a project (or across projects only if cross_project=True)."""
        target_projects: list[str] = []

        if cross_project or project_id == "*":
            # Explicit cross-project search requested
            target_projects = [p.project_id for p in self.project_svc.list_projects()]
        else:
            if not project_id or not project_id.strip():
                raise ValidationError("project_id is required unless cross_project=True.")
            p_dir = self.project_svc.get_project_dir(project_id)
            if not (p_dir / "PROJECT.md").exists():
                raise ProjectNotFoundError(f"Project '{project_id}' does not exist.")
            target_projects = [project_id.strip()]

        # Parse type filter
        type_filter: str | None = None
        if type:
            type_filter = type.value if isinstance(type, MemoryType) else str(type).lower().strip()

        # Parse status filter
        status_filter: str | None = None
        if status:
            status_filter = status.value if isinstance(status, MemoryStatus) else str(status).lower().strip()

        # Parse time filters
        dt_start: datetime | None = None
        if time_start:
            dt_start = datetime.fromisoformat(str(time_start)) if isinstance(time_start, str) else time_start

        dt_end: datetime | None = None
        if time_end:
            dt_end = datetime.fromisoformat(str(time_end)) if isinstance(time_end, str) else time_end

        query_tokens = [t.lower() for t in re.split(r"\s+", query.strip())] if query and query.strip() else []

        hits: list[SearchHit] = []

        for pid in target_projects:
            p_dir = self.project_svc.get_project_dir(pid)
            for sub in SUBDIRS:
                sub_dir = p_dir / sub
                if not sub_dir.exists():
                    continue

                for md_file in sorted(sub_dir.glob("*.md")):
                    try:
                        content = md_file.read_text(encoding="utf-8")
                        meta, body = parse_frontmatter(content)
                        if "id" not in meta or "type" not in meta:
                            continue

                        fm = MemoryFrontmatter.model_validate(meta)

                        # Filter by type
                        if type_filter and fm.type.value != type_filter:
                            continue

                        # Filter by status
                        if status_filter and fm.status.value != status_filter:
                            continue

                        # Filter by time
                        if dt_start and fm.created_at < dt_start:
                            continue
                        if dt_end and fm.created_at > dt_end:
                            continue

                        # Filter by tags
                        if tags:
                            fm_tags_lower = [t.lower() for t in fm.tags]
                            if not any(req_tag.lower() in fm_tags_lower for req_tag in tags):
                                continue

                        # Relevance scoring
                        score = 0.0
                        reasons: list[str] = []

                        if not query_tokens:
                            # No keyword query: base score
                            score = 1.0
                            reasons.append("Matched metadata filters")
                        else:
                            # Check ID match
                            if any(q == fm.id.lower() for q in query_tokens):
                                score += 10.0
                                reasons.append("Exact Memory ID match")

                            # Check Title match
                            title_lower = fm.title.lower()
                            title_matches = [q for q in query_tokens if q in title_lower]
                            if title_matches:
                                score += 5.0 * len(title_matches)
                                reasons.append(f"Title matched tokens: {title_matches}")

                            # Check Tags match
                            tag_matches = [q for q in query_tokens if any(q in t.lower() for t in fm.tags)]
                            if tag_matches:
                                score += 3.0 * len(tag_matches)
                                reasons.append(f"Tags matched: {tag_matches}")

                            # Check Body content match
                            body_lower = body.lower()
                            body_matches = [q for q in query_tokens if q in body_lower]
                            if body_matches:
                                score += 1.0 * len(body_matches)
                                reasons.append(f"Body matched tokens: {body_matches}")

                            # If no tokens matched at all, skip
                            if score <= 0.0:
                                continue

                        # Extract snippet
                        snippet = self._make_snippet(body, query_tokens)
                        rel_path = md_file.relative_to(p_dir).as_posix()

                        hit = SearchHit(
                            memory_id=fm.id,
                            project_id=pid,
                            type=fm.type.value,
                            title=fm.title,
                            snippet=snippet,
                            file_path=rel_path,
                            created_at=fm.created_at.isoformat(),
                            score=score,
                            relevance_reasons=reasons,
                        )
                        hits.append(hit)
                    except Exception:
                        continue

        # Sort hits by score descending, then by created_at descending
        hits.sort(key=lambda x: (x.score, x.created_at), reverse=True)
        return hits[:limit]

    def _make_snippet(self, body: str, query_tokens: list[str], max_chars: int = 160) -> str:
        """Generates a contextual snippet around matching tokens or from the start of body."""
        clean = re.sub(r"\s+", " ", body).strip()
        if not clean:
            return ""

        if not query_tokens:
            return clean[:max_chars] + ("..." if len(clean) > max_chars else "")

        lower = clean.lower()
        first_idx = len(clean)
        for t in query_tokens:
            idx = lower.find(t)
            if idx != -1 and idx < first_idx:
                first_idx = idx

        if first_idx == len(clean) or first_idx < max_chars // 2:
            return clean[:max_chars] + ("..." if len(clean) > max_chars else "")

        start = max(0, first_idx - 40)
        end = min(len(clean), start + max_chars)
        return f"...{clean[start:end]}..."
