"""Finding management service for evidence-backed empirical discoveries."""

from pathlib import Path
from typing import Any

from researchos.core.enums import (
    FindingStatus,
    IdPrefix,
)
from researchos.core.exceptions import (
    EntityNotFoundError,
    ValidationError,
)
from researchos.core.ids import IdGenerator
from researchos.core.models import (
    Experiment,
    Finding,
    utc_now,
)
from researchos.storage.markdown_store import MarkdownStore


class FindingService:
    """Manages empirical findings linked to experiments, runs, and artifacts."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.store = MarkdownStore(self.vault_root)
        self.id_gen = IdGenerator(self.vault_root)

    def create_finding(
        self,
        project_id: str,
        experiment_id: str,
        title: str,
        summary: str | None = None,
        run_id: str | None = None,
        evidence_artifacts: list[str] | None = None,
        literature: list[str] | None = None,
        research_question: str | None = None,
        status: FindingStatus = FindingStatus.CANDIDATE,
    ) -> Finding:
        if not title or not title.strip():
            raise ValidationError("Finding title cannot be empty.")

        exp_path = self.store.resolve_entity_path(experiment_id, project_id=project_id)
        if not exp_path.exists():
            raise EntityNotFoundError(f"Experiment {experiment_id} not found.")

        exp, exp_body = self.store.load_entity(exp_path, Experiment)

        finding_id = self.id_gen.generate_id(IdPrefix.FINDING)
        finding = Finding(
            id=finding_id,
            project_id=project_id,
            experiment_id=experiment_id,
            run_id=run_id,
            title=title.strip(),
            status=status,
            evidence_artifacts=evidence_artifacts or [],
            literature=literature or [],
            research_question=research_question or exp.research_question,
        )

        tpl_path = self.vault_root / "90-Templates" / "finding.md"
        body = tpl_path.read_text(encoding="utf-8") if tpl_path.exists() else "# {id} {title}\n\n## Summary\n"
        body = body.replace("{id}", finding.id).replace("{title}", finding.title)

        if summary:
            body = body.replace("## Summary", f"## Summary\n{summary}")

        find_path = self.store.resolve_entity_path(finding.id, project_id=project_id)
        self.store.save_entity(finding, body, path=find_path)

        # Update experiment's findings
        if finding.id not in exp.findings:
            exp.findings.append(finding.id)
            self.store.save_entity(exp, exp_body, path=exp_path)

        return finding

    def get_finding(self, finding_id: str) -> tuple[Finding, str]:
        path = self.store.resolve_entity_path(finding_id)
        if not path.exists():
            raise EntityNotFoundError(f"Finding {finding_id} not found.")
        return self.store.load_entity(path, Finding)
