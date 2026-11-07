"""Literature management service for self-contained, Zotero-free bibliography tracking."""

from pathlib import Path
from typing import Any

from researchos.core.enums import (
    IdPrefix,
    PaperReadingStatus,
)
from researchos.core.exceptions import (
    EntityNotFoundError,
    ValidationError,
)
from researchos.core.ids import IdGenerator
from researchos.core.models import (
    Paper,
    utc_now,
)
from researchos.storage.markdown_store import MarkdownStore


class PaperService:
    """Manages literature notes, BibTeX citekeys, and direct experiment citations."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.store = MarkdownStore(self.vault_root)
        self.id_gen = IdGenerator(self.vault_root)

    def create_paper(
        self,
        title: str,
        citekey: str,
        authors: list[str] | None = None,
        year: int | None = None,
        journal: str | None = None,
        doi: str | None = None,
        url: str | None = None,
        pdf_path: str | None = None,
        abstract: str | None = None,
        reading_status: PaperReadingStatus = PaperReadingStatus.TO_READ,
        projects: list[str] | None = None,
        related_experiments: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> Paper:
        if not title or not title.strip():
            raise ValidationError("Paper title cannot be empty.")
        if not citekey or not citekey.strip():
            raise ValidationError("Paper citekey cannot be empty.")

        paper_id = self.id_gen.generate_id(IdPrefix.PAPER)
        paper = Paper(
            id=paper_id,
            citekey=citekey.strip(),
            title=title.strip(),
            authors=authors or [],
            year=year,
            journal=journal,
            doi=doi,
            url=url,
            pdf_path=pdf_path,
            abstract=abstract,
            reading_status=reading_status,
            projects=projects or [],
            related_experiments=related_experiments or [],
            tags=tags or [],
        )

        tpl_path = self.vault_root / "90-Templates" / "paper.md"
        body = tpl_path.read_text(encoding="utf-8") if tpl_path.exists() else "# {title}\n\n## Bibliographic Information\n"
        body = body.replace("{title}", paper.title).replace("{id}", paper.id)

        if abstract:
            body = body.replace("## Main Findings", f"## Abstract\n{abstract}\n\n## Main Findings")

        paper_path = self.store.resolve_entity_path(paper.id)
        self.store.save_entity(paper, body, path=paper_path)
        return paper

    def get_paper(self, identifier: str) -> tuple[Paper, str]:
        """Looks up a paper by Paper ID or Citekey."""
        lit_dir = self.vault_root / "01-Literature"
        if not lit_dir.exists():
            raise EntityNotFoundError(f"Paper '{identifier}' not found.")

        # If it's a PAPER-ID
        direct_path = lit_dir / f"{identifier}.md"
        if direct_path.exists():
            return self.store.load_entity(direct_path, Paper)

        # Otherwise search by citekey
        for f in lit_dir.glob("*.md"):
            try:
                p, body = self.store.load_entity(f, Paper)
                if p.citekey.lower() == identifier.lower() or p.id == identifier:
                    return p, body
            except Exception:
                continue

        raise EntityNotFoundError(f"Paper '{identifier}' not found in {lit_dir}.")

    def search_papers(
        self,
        query: str,
        tags: list[str] | None = None,
        reading_status: PaperReadingStatus | None = None,
    ) -> list[Paper]:
        lit_dir = self.vault_root / "01-Literature"
        if not lit_dir.exists():
            return []

        q = query.lower().strip()
        matched: list[Paper] = []
        for f in sorted(lit_dir.glob("*.md")):
            try:
                paper, body = self.store.load_entity(f, Paper)
                if reading_status and paper.reading_status != reading_status:
                    continue
                if tags and not any(t in paper.tags for t in tags):
                    continue

                # Search in title, citekey, authors, abstract, body
                haystack = f"{paper.title} {paper.citekey} {' '.join(paper.authors)} {paper.abstract or ''} {body}".lower()
                if not q or q in haystack:
                    matched.append(paper)
            except Exception:
                continue
        return matched

    def link_paper(
        self,
        paper_id: str,
        project_id: str | None = None,
        experiment_id: str | None = None,
    ) -> Paper:
        paper, body = self.get_paper(paper_id)
        updated = False
        if project_id and project_id not in paper.projects:
            paper.projects.append(project_id)
            updated = True
        if experiment_id and experiment_id not in paper.related_experiments:
            paper.related_experiments.append(experiment_id)
            updated = True

        if updated:
            path = self.store.resolve_entity_path(paper.id)
            self.store.save_entity(paper, body, path=path)
        return paper
