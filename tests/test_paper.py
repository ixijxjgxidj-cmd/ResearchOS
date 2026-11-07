"""Tests for Literature Paper notes, metadata, and citation linkages."""

from pathlib import Path
from researchos.core.enums import PaperReadingStatus
from researchos.services.paper_service import PaperService
from researchos.services.project_service import ProjectService


def test_paper_create_and_search(vault_dir: Path, paper_service: PaperService, project_service: ProjectService):
    proj = project_service.create_project(name="Attention Research")

    # Ingest paper
    paper = paper_service.create_paper(
        title="Attention Is All You Need",
        citekey="vaswani2017attention",
        authors=["Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit"],
        year=2017,
        doi="10.5555/3295222.3295349",
        abstract="The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...",
        reading_status=PaperReadingStatus.READ,
        projects=[proj.id],
    )

    assert paper.id.startswith("PAPER-")
    assert paper.citekey == "vaswani2017attention"
    assert (vault_dir / "01-Literature" / f"{paper.id}.md").exists()

    # Retrieve by citekey
    fetched_by_citekey, _ = paper_service.get_paper("vaswani2017attention")
    assert fetched_by_citekey.id == paper.id

    # Retrieve by ID
    fetched_by_id, body = paper_service.get_paper(paper.id)
    assert fetched_by_id.title == "Attention Is All You Need"
    assert "Bibliographic Information" in body

    # Search by keyword
    results = paper_service.search_papers("dominant sequence transduction")
    assert len(results) == 1
    assert results[0].id == paper.id

    # Search with no match
    no_results = paper_service.search_papers("quantum teleportation")
    assert len(no_results) == 0
