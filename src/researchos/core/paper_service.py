"""Paper Writing Mode service for structured experiment inventory, section filtering, and evidence coverage tracking."""

from pathlib import Path
from typing import Any

from researchos.core.memory_service import MemoryService
from researchos.core.project_service import ProjectService
from researchos.core.storage_service import parse_frontmatter
from researchos.models.memory import (
    EvidenceCoverage,
    MemoryFrontmatter,
    MemoryStatus,
    MemoryType,
    PaperExperimentItem,
)
from researchos.utils.exceptions import ProjectNotFoundError


class PaperService:
    """Manages Paper Writing Mode workflows, experiment inventory, and evidence coverage."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.project_svc = ProjectService(self.vault_root)
        self.memory_svc = MemoryService(self.vault_root)

    def get_paper_inventory(
        self,
        project_id: str,
        paper_section: str | None = None,
        status_filter: list[str] | None = None,
    ) -> list[PaperExperimentItem]:
        """Phase A & B: Returns a lightweight metadata inventory of all experiments.

        Includes Completed, Failed, Interrupted, Running, and Superseded experiments.
        Does not load heavy full markdown bodies.
        """
        p_dir = self.project_svc.get_project_dir(project_id)
        if not (p_dir / "PROJECT.md").exists():
            raise ProjectNotFoundError(f"Project '{project_id}' does not exist.")

        inventory: list[PaperExperimentItem] = []
        status_filter_lower = [s.lower().strip() for s in status_filter] if status_filter else None
        target_section_lower = paper_section.lower().strip() if paper_section else None

        # Scan observations, negative, and decisions
        for sub in ("observations", "negative", "decisions", "archive"):
            sub_dir = p_dir / sub
            if not sub_dir.exists():
                continue

            for f in sorted(sub_dir.glob("*.md")):
                try:
                    content = f.read_text(encoding="utf-8")
                    meta, _ = parse_frontmatter(content)
                    if "id" not in meta or "type" not in meta:
                        continue

                    fm = MemoryFrontmatter.model_validate(meta)

                    # Determine fine-grained status (Completed, Failed, Interrupted, Running, Superseded)
                    tags_lower = [t.lower() for t in fm.tags]
                    calc_status = "completed"
                    if fm.status == MemoryStatus.SUPERSEDED:
                        calc_status = "superseded"
                    elif fm.status == MemoryStatus.ARCHIVED:
                        calc_status = "archived"
                    elif fm.type == MemoryType.NEGATIVE or "failed" in tags_lower:
                        calc_status = "failed"
                    elif "interrupted" in tags_lower:
                        calc_status = "interrupted"
                    elif "running" in tags_lower:
                        calc_status = "running"

                    # Status filter
                    if status_filter_lower and calc_status not in status_filter_lower:
                        continue

                    # Section filter
                    item_section = fm.paper_section or ""
                    if target_section_lower and target_section_lower not in item_section.lower():
                        # Also check if section title or tag matches
                        if target_section_lower not in fm.title.lower() and not any(
                            target_section_lower in t for t in tags_lower
                        ):
                            continue

                    # Collect related literature
                    related_lit = [r for r in fm.related if r.startswith("REF-") or "ref" in r.lower()]
                    if fm.source_ref and fm.source_ref.startswith(("10.", "http://", "https://", "arXiv")):
                        related_lit.append(fm.source_ref)

                    item = PaperExperimentItem(
                        memory_id=fm.id,
                        experiment_id=fm.experiment_id or (fm.source_ref if fm.source_ref and "run" in fm.source_ref.lower() else None),
                        title=fm.title,
                        status=calc_status,
                        paper_section=fm.paper_section,
                        metrics_summary=fm.metrics_summary,
                        related_literature=related_lit,
                        parent_experiment=fm.parent_experiment,
                        artifact_paths=fm.artifact_paths,
                        created_at=fm.created_at.isoformat(),
                    )
                    inventory.append(item)
                except Exception:
                    continue

        return inventory

    def get_section_categorized_evidence(
        self,
        project_id: str,
        paper_section: str,
    ) -> dict[str, Any]:
        """Phase B: Gathers and categorizes evidence for a specific paper section."""
        items = self.get_paper_inventory(project_id, paper_section=paper_section)

        baselines = []
        ablations = []
        comparatives = []
        failed = []
        superseded = []
        standard = []

        for it in items:
            t_lower = it.title.lower()
            if it.status == "failed":
                failed.append(it)
            elif it.status == "superseded":
                superseded.append(it)
            elif "baseline" in t_lower:
                baselines.append(it)
            elif "ablation" in t_lower:
                ablations.append(it)
            elif "vs" in t_lower or "comparison" in t_lower or "compare" in t_lower:
                comparatives.append(it)
            else:
                standard.append(it)

        return {
            "project_id": project_id,
            "paper_section": paper_section,
            "total_candidates": len(items),
            "baseline_experiments": [b.model_dump() for b in baselines],
            "ablation_experiments": [a.model_dump() for a in ablations],
            "comparative_experiments": [c.model_dump() for c in comparatives],
            "failed_experiments": [f.model_dump() for f in failed],
            "superseded_experiments": [s.model_dump() for s in superseded],
            "standard_experiments": [st.model_dump() for st in standard],
        }

    def check_evidence_coverage(
        self,
        project_id: str,
        paper_section: str,
        loaded_memory_ids: list[str],
        excluded_memory_ids: dict[str, str] | None = None,
    ) -> EvidenceCoverage:
        """Phase D: Validates Evidence Coverage for a paper section before drafting begins.

        Ensures no target experiment or negative outcome was silently overlooked.
        """
        inventory = self.get_paper_inventory(project_id, paper_section=paper_section)
        target_ids = [item.memory_id for item in inventory]

        loaded_set = set(loaded_memory_ids)
        excluded_dict = excluded_memory_ids or {}

        pending_ids = [mid for mid in target_ids if mid not in loaded_set and mid not in excluded_dict]
        missing_evidence = []
        for pid in pending_ids:
            item_match = next((i for i in inventory if i.memory_id == pid), None)
            desc = f"{pid}: {item_match.title} [{item_match.status}]" if item_match else pid
            missing_evidence.append(desc)

        # Check physical existence of raw artifacts cited by loaded memories
        p_dir = self.project_svc.get_project_dir(project_id)
        missing_artifacts = []
        for lid in loaded_set:
            match = next((i for i in inventory if i.memory_id == lid), None)
            if match and match.artifact_paths:
                for art in match.artifact_paths:
                    art_path = (p_dir / art).resolve()
                    if not art_path.exists() and not Path(art).exists():
                        missing_artifacts.append(f"{lid} -> missing artifact {art}")

        is_fully_covered = len(pending_ids) == 0 and len(missing_artifacts) == 0

        return EvidenceCoverage(
            project_id=project_id,
            paper_section=paper_section,
            target_memory_ids=target_ids,
            loaded_memory_ids=list(loaded_set),
            pending_memory_ids=pending_ids,
            excluded_memory_ids=excluded_dict,
            is_fully_covered=is_fully_covered,
            missing_evidence=missing_evidence,
            missing_artifacts=missing_artifacts,
        )
