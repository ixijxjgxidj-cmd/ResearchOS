"""Memory retrieval, BM25 ranking, and relation graph search service with strict project isolation."""

import math
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from researchos.core.project_service import SUBDIRS, ProjectService
from researchos.core.storage_service import parse_frontmatter
from researchos.models.memory import (
    MemoryFrontmatter,
    MemoryStatus,
    MemoryType,
)
from researchos.utils.exceptions import MemoryNotFoundError, ProjectNotFoundError, ValidationError

# Regex to match CJK unified ideographs
CJK_REGEX = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
# Regex to match Latin/alphanumeric tokens, model identifiers, DOIs
WORD_REGEX = re.compile(r"[a-zA-Z0-9_\-\.]+")
# Punctuation to normalize into spaces
PUNCTUATION_REGEX = re.compile(r"[\s\.,;:!\?\"'’“”«»\(\)\[\]\{\}\<\>\\/\|\`\~\@\#\$\%\^\&\*\+\=\—\-\_，。！？；：“”‘’（）《》【】、]+")


def tokenize_text(text: str) -> list[str]:
    """Tokenizes mixed CJK/Latin/scientific text.

    Strategies:
      1. Unicode NFKC normalization and lowercasing.
      2. Latin/alphanumeric word matching (preserving terms like 'llama-3.1', 'gpt-4o', 'gsm8k').
      3. CJK 1-grams (individual characters) and 2-grams (adjacent pairs for phrase matching).
    """
    if not text:
        return []

    normalized = unicodedata.normalize("NFKC", text).lower()
    tokens: list[str] = []

    # 1. Alphanumeric/Latin terms
    for match in WORD_REGEX.finditer(normalized):
        token = match.group(0).strip(".-_")
        if len(token) > 1:
            tokens.append(token)

    # 2. CJK character sequences
    cjk_chars: list[str] = []
    for ch in normalized:
        if CJK_REGEX.match(ch):
            cjk_chars.append(ch)
            tokens.append(ch)  # 1-gram
        else:
            if len(cjk_chars) > 1:
                # Add 2-grams for accumulated CJK sequence
                for i in range(len(cjk_chars) - 1):
                    tokens.append("".join(cjk_chars[i : i + 2]))
            cjk_chars = []

    if len(cjk_chars) > 1:
        for i in range(len(cjk_chars) - 1):
            tokens.append("".join(cjk_chars[i : i + 2]))

    return tokens


class BM25Scorer:
    """Pure-Python BM25 Okapi scorer for in-memory document ranking."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b

    def compute_idf(self, corpus_doc_tokens: list[list[str]]) -> dict[str, float]:
        """Calculates smoothed IDF for all unique tokens across the corpus."""
        n_docs = len(corpus_doc_tokens)
        df: Counter[str] = Counter()
        for doc_tokens in corpus_doc_tokens:
            unique_terms = set(doc_tokens)
            df.update(unique_terms)

        idf: dict[str, float] = {}
        for term, freq in df.items():
            # BM25 smoothed IDF formula
            idf[term] = math.log(1.0 + (n_docs - freq + 0.5) / (freq + 0.5))
        return idf

    def score_document(
        self,
        doc_tokens: list[str],
        query_tokens: list[str],
        idf: dict[str, float],
        avg_dl: float,
    ) -> float:
        """Scores a document against query tokens using BM25."""
        if not doc_tokens or not query_tokens or avg_dl == 0:
            return 0.0

        dl = len(doc_tokens)
        doc_freq = Counter(doc_tokens)
        score = 0.0

        for q in query_tokens:
            if q not in doc_freq:
                continue
            tf = doc_freq[q]
            term_idf = idf.get(q, 0.0)
            numerator = tf * (self.k1 + 1.0)
            denominator = tf + self.k1 * (1.0 - self.b + self.b * (dl / avg_dl))
            score += term_idf * (numerator / denominator)

        return score


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


class RelationHit(BaseModel):
    """Result item from a relation graph traversal."""

    memory_id: str
    project_id: str
    type: str
    title: str
    relation_type: str
    depth: int
    direction: str
    file_path: str


class RetrievalService:
    """Performs isolated in-project searches, BM25 ranking, and relation graph traversal."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.project_svc = ProjectService(self.vault_root)
        self.bm25 = BM25Scorer(k1=1.5, b=0.75)

    def search_memories(
        self,
        project_id: str,
        query: str | None = None,
        type: MemoryType | str | None = None,
        tags: list[str] | None = None,
        tag_mode: Literal["OR", "AND"] = "OR",
        status: MemoryStatus | str | None = None,
        source_agent: str | None = None,
        source_skill: str | None = None,
        source_type: str | None = None,
        min_confidence: float | None = None,
        time_start: datetime | str | None = None,
        time_end: datetime | str | None = None,
        limit: int = 20,
        cross_project: bool = False,
    ) -> list[SearchHit]:
        """Searches memories within a project (or across projects if cross_project=True).

        Applies BM25 ranking with field weighting:
          - Exact ID match boost: +15.0
          - Title field weight: 5.0
          - Tags field weight: 3.0
          - Snippet / Summary weight: 2.0
          - Body content weight: 1.0
        """
        target_projects: list[str] = []

        if cross_project or project_id == "*":
            target_projects = [p.project_id for p in self.project_svc.list_projects()]
        else:
            if not project_id or not project_id.strip():
                raise ValidationError("project_id is required unless cross_project=True.")
            p_dir = self.project_svc.get_project_dir(project_id)
            if not (p_dir / "PROJECT.md").exists():
                raise ProjectNotFoundError(f"Project '{project_id}' does not exist.")
            target_projects = [project_id.strip()]

        type_filter = type.value if isinstance(type, MemoryType) else (str(type).lower().strip() if type else None)
        status_filter = status.value if isinstance(status, MemoryStatus) else (str(status).lower().strip() if status else None)

        dt_start: datetime | None = None
        if time_start:
            dt_start = datetime.fromisoformat(str(time_start)) if isinstance(time_start, str) else time_start

        dt_end: datetime | None = None
        if time_end:
            dt_end = datetime.fromisoformat(str(time_end)) if isinstance(time_end, str) else time_end

        query_tokens = tokenize_text(query) if query and query.strip() else []
        query_raw_lower = query.lower().strip() if query and query.strip() else ""

        # Step 1: Collect candidates passing hard metadata filters
        candidates: list[dict[str, Any]] = []

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

                        if type_filter and fm.type.value != type_filter:
                            continue
                        fm_stat = fm.status.value if hasattr(fm.status, "value") else str(fm.status)
                        if status_filter and fm_stat != status_filter:
                            continue
                        if dt_start and fm.created_at < dt_start:
                            continue
                        if dt_end and fm.created_at > dt_end:
                            continue
                        if source_agent and (not fm.source_agent or fm.source_agent.lower() != source_agent.lower()):
                            continue
                        if source_skill and (not fm.source_skill or fm.source_skill.lower() != source_skill.lower()):
                            continue
                        if source_type:
                            st_val = fm.source_type.value if hasattr(fm.source_type, "value") else str(fm.source_type)
                            if not st_val or st_val.lower() != source_type.lower():
                                continue
                        if min_confidence is not None:
                            if fm.confidence is None or fm.confidence < min_confidence:
                                continue

                        if tags:
                            fm_tags_lower = [t.lower() for t in fm.tags]
                            req_tags_lower = [t.lower() for t in tags]
                            if tag_mode == "AND":
                                if not all(t in fm_tags_lower for t in req_tags_lower):
                                    continue
                            else:
                                if not any(t in fm_tags_lower for t in req_tags_lower):
                                    continue

                        rel_path = md_file.relative_to(p_dir).as_posix()
                        candidates.append({
                            "fm": fm,
                            "body": body,
                            "file_path": rel_path,
                            "project_id": pid,
                            "md_file": md_file,
                        })
                    except Exception:
                        continue

        if not candidates:
            return []

        # Step 2: Scoring
        if not query_tokens:
            # Metadata-only matching
            hits: list[SearchHit] = []
            for item in candidates:
                fm = item["fm"]
                snippet = self._make_snippet(item["body"], [])
                hits.append(
                    SearchHit(
                        memory_id=fm.id,
                        project_id=item["project_id"],
                        type=fm.type.value,
                        title=fm.title,
                        snippet=snippet,
                        file_path=item["file_path"],
                        created_at=fm.created_at.isoformat(),
                        score=1.0,
                        relevance_reasons=["Matched metadata filters"],
                    )
                )
            hits.sort(key=lambda x: x.created_at, reverse=True)
            return hits[:limit]

        # BM25 Corpus Preparation
        # Tokenize fields for each candidate document
        doc_body_tokens = [tokenize_text(c["body"]) for c in candidates]
        doc_title_tokens = [tokenize_text(c["fm"].title) for c in candidates]

        # Calculate IDF based on body tokens corpus
        idf = self.bm25.compute_idf(doc_body_tokens)
        avg_body_len = sum(len(dt) for dt in doc_body_tokens) / max(len(doc_body_tokens), 1)
        avg_title_len = sum(len(dt) for dt in doc_title_tokens) / max(len(doc_title_tokens), 1)

        hits = []
        for idx, item in enumerate(candidates):
            fm: MemoryFrontmatter = item["fm"]
            body: str = item["body"]
            reasons: list[str] = []
            score = 0.0

            # 1. Exact ID Match (Highest Priority)
            if fm.id.lower() == query_raw_lower or any(q == fm.id.lower() for q in query_tokens):
                score += 15.0
                reasons.append("Exact Memory ID match")

            # 2. Title Match (BM25 weighted * 5.0 + exact substring boost)
            title_score = self.bm25.score_document(
                doc_title_tokens[idx], query_tokens, idf, avg_title_len
            )
            if query_raw_lower in fm.title.lower():
                title_score += 3.0
                reasons.append(f"Title contains exact phrase: '{query_raw_lower}'")
            elif title_score > 0:
                reasons.append(f"Title matched terms (score: {title_score:.2f})")
            score += title_score * 5.0

            # 3. Tags Match (Weight * 3.0)
            tag_matches = [t for t in fm.tags if any(q in t.lower() for q in query_tokens)]
            if tag_matches:
                score += 3.0 * len(tag_matches)
                reasons.append(f"Tags matched: {tag_matches}")

            # 4. Body Content BM25 Match (Weight * 1.0 + exact substring boost)
            body_score = self.bm25.score_document(
                doc_body_tokens[idx], query_tokens, idf, avg_body_len
            )
            if query_raw_lower in body.lower():
                body_score += 2.0
                reasons.append(f"Body contains exact phrase: '{query_raw_lower}'")
            elif body_score > 0:
                reasons.append(f"Body BM25 matched (score: {body_score:.2f})")
            score += body_score * 1.0

            if score <= 0.0:
                continue

            snippet = self._make_snippet(body, query_tokens)
            hits.append(
                SearchHit(
                    memory_id=fm.id,
                    project_id=item["project_id"],
                    type=fm.type.value,
                    title=fm.title,
                    snippet=snippet,
                    file_path=item["file_path"],
                    created_at=fm.created_at.isoformat(),
                    score=round(score, 4),
                    relevance_reasons=reasons,
                )
            )

        hits.sort(key=lambda x: (x.score, x.created_at), reverse=True)
        return hits[:limit]

    def search_related_graph(
        self,
        project_id: str,
        memory_id: str,
        max_depth: int = 1,
        direction: Literal["outbound", "inbound", "both"] = "both",
    ) -> list[RelationHit]:
        """Traverses the memory relation graph (related, supersedes, superseded_by) within project boundary.

        Features:
          - Enforces strict project isolation boundary.
          - Depth limit: clamped between 1 and 3 to prevent excessive traversal.
          - Cycle detection: avoids infinite loops.
        """
        p_dir = self.project_svc.get_project_dir(project_id)
        if not (p_dir / "PROJECT.md").exists():
            raise ProjectNotFoundError(f"Project '{project_id}' does not exist.")

        # Load all project memories into an index map for quick lookup
        all_memories: dict[str, tuple[MemoryFrontmatter, str]] = {}
        for sub in SUBDIRS:
            sub_dir = p_dir / sub
            if not sub_dir.exists():
                continue
            for f in sub_dir.glob("*.md"):
                try:
                    content = f.read_text(encoding="utf-8")
                    meta, _ = parse_frontmatter(content)
                    if "id" in meta and "type" in meta:
                        fm = MemoryFrontmatter.model_validate(meta)
                        rel_path = f.relative_to(p_dir).as_posix()
                        all_memories[fm.id] = (fm, rel_path)
                except Exception:
                    continue

        if memory_id not in all_memories:
            raise MemoryNotFoundError(
                f"Memory '{memory_id}' not found in project '{project_id}'."
            )

        effective_depth = max(1, min(max_depth, 3))
        visited: set[str] = {memory_id}
        hits: list[RelationHit] = []

        # BFS Queue: (current_memory_id, current_depth)
        queue: list[tuple[str, int]] = [(memory_id, 0)]

        while queue:
            curr_id, curr_depth = queue.pop(0)
            if curr_depth >= effective_depth:
                continue

            curr_fm = all_memories[curr_id][0]

            # Outbound links (curr_id -> targets)
            if direction in ("outbound", "both"):
                # related
                for rel_id in curr_fm.related:
                    if rel_id in all_memories and rel_id not in visited:
                        visited.add(rel_id)
                        target_fm, target_path = all_memories[rel_id]
                        hits.append(
                            RelationHit(
                                memory_id=target_fm.id,
                                project_id=project_id,
                                type=target_fm.type.value,
                                title=target_fm.title,
                                relation_type="related",
                                depth=curr_depth + 1,
                                direction="outbound",
                                file_path=target_path,
                            )
                        )
                        queue.append((rel_id, curr_depth + 1))

                # supersedes
                if curr_fm.supersedes and curr_fm.supersedes in all_memories and curr_fm.supersedes not in visited:
                    visited.add(curr_fm.supersedes)
                    target_fm, target_path = all_memories[curr_fm.supersedes]
                    hits.append(
                        RelationHit(
                            memory_id=target_fm.id,
                            project_id=project_id,
                            type=target_fm.type.value,
                            title=target_fm.title,
                            relation_type="supersedes",
                            depth=curr_depth + 1,
                            direction="outbound",
                            file_path=target_path,
                        )
                    )
                    queue.append((curr_fm.supersedes, curr_depth + 1))

                # superseded_by
                if curr_fm.superseded_by and curr_fm.superseded_by in all_memories and curr_fm.superseded_by not in visited:
                    visited.add(curr_fm.superseded_by)
                    target_fm, target_path = all_memories[curr_fm.superseded_by]
                    hits.append(
                        RelationHit(
                            memory_id=target_fm.id,
                            project_id=project_id,
                            type=target_fm.type.value,
                            title=target_fm.title,
                            relation_type="superseded_by",
                            depth=curr_depth + 1,
                            direction="outbound",
                            file_path=target_path,
                        )
                    )
                    queue.append((curr_fm.superseded_by, curr_depth + 1))

            # Inbound links (sources -> curr_id)
            if direction in ("inbound", "both"):
                for cand_id, (cand_fm, cand_path) in all_memories.items():
                    if cand_id in visited:
                        continue

                    is_inbound = False
                    rel_kind = "inbound_related"

                    if curr_id in cand_fm.related:
                        is_inbound = True
                        rel_kind = "referenced_by"
                    elif cand_fm.supersedes == curr_id:
                        is_inbound = True
                        rel_kind = "superseded_by"
                    elif cand_fm.superseded_by == curr_id:
                        is_inbound = True
                        rel_kind = "supersedes"

                    if is_inbound:
                        visited.add(cand_id)
                        hits.append(
                            RelationHit(
                                memory_id=cand_fm.id,
                                project_id=project_id,
                                type=cand_fm.type.value,
                                title=cand_fm.title,
                                relation_type=rel_kind,
                                depth=curr_depth + 1,
                                direction="inbound",
                                file_path=cand_path,
                            )
                        )
                        queue.append((cand_id, curr_depth + 1))

        return hits

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
