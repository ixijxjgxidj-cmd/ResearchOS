"""Experiment management service for hypothesis testing and protocol lifecycle."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from researchos.core.enums import (
    ExperimentOutcome,
    ExperimentStatus,
    IdPrefix,
)
from researchos.core.exceptions import (
    EntityNotFoundError,
    ValidationError,
)
from researchos.core.ids import IdGenerator
from researchos.core.models import (
    Experiment,
    Project,
    utc_now,
)
from researchos.services.validation_service import ValidationService
from researchos.storage.atomic_writer import atomic_write_text
from researchos.storage.markdown_store import MarkdownStore


class ExperimentService:
    """Manages experiment specifications, lifecycle transitions, and run attachments."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.store = MarkdownStore(self.vault_root)
        self.id_gen = IdGenerator(self.vault_root)
        self.validation = ValidationService()

    def create_experiment(
        self,
        project_id: str,
        title: str,
        objective: str | None = None,
        research_question: str | None = None,
        hypothesis: str | None = None,
        rationale: str | None = None,
        literature: list[str] | None = None,
        execution: dict[str, Any] | None = None,
        method: str | None = None,
        planned_parameters: dict[str, Any] | None = None,
        expected_result: str | None = None,
        success_criteria: list[str] | None = None,
        inputs: list[str] | None = None,
        planned_outputs: list[str] | None = None,
        is_exploratory: bool = False,
    ) -> Experiment:
        """Creates a new Experiment entity under the specified project."""
        proj_path = self.store.resolve_entity_path(project_id)
        if not proj_path.exists():
            raise EntityNotFoundError(f"Parent project {project_id} does not exist.")

        proj, proj_body = self.store.load_entity(proj_path, Project)

        exp_id = self.id_gen.generate_id(IdPrefix.EXPERIMENT)
        exp = Experiment(
            id=exp_id,
            project_id=project_id,
            title=title.strip(),
            status=ExperimentStatus.PLANNED,
            outcome=ExperimentOutcome.PENDING,
            is_exploratory=is_exploratory,
            objective=objective,
            research_question=research_question or proj.research_question,
            hypothesis=hypothesis,
            rationale=rationale,
            literature=literature or [],
            execution=execution or {},
            method=method,
            planned_parameters=planned_parameters or {},
            expected_result=expected_result,
            success_criteria=success_criteria or [],
            inputs=inputs or [],
            planned_outputs=planned_outputs or [],
        )

        tpl_path = self.vault_root / "90-Templates" / "experiment.md"
        body = tpl_path.read_text(encoding="utf-8") if tpl_path.exists() else "# {id} {title}\n\n## 1. Why\n\n## 2. Research Question\n"
        body = body.replace("{id}", exp.id).replace("{title}", exp.title)

        # Inject populated values into template sections if provided
        if rationale or objective:
            body = body.replace("为什么要做这个实验？", (rationale or objective or "").strip())
        if exp.research_question:
            body = body.replace("研究问题。", exp.research_question.strip())
        if exp.hypothesis:
            body = body.replace("研究假设。", exp.hypothesis.strip())
        if exp.method:
            body = body.replace("实验方法和步骤。", exp.method.strip())
        if exp.expected_result:
            body = body.replace("预期结果。", exp.expected_result.strip())

        exp_path = self.store.resolve_entity_path(exp.id, project_id=project_id)
        self.store.save_entity(exp, body, path=exp_path)

        # Update parent project's experiments list
        if exp_id not in proj.experiments:
            proj.experiments.append(exp_id)
            self.store.save_entity(proj, proj_body, path=proj_path)

        # Append to project CHANGELOG.md
        changelog_path = self.store.get_project_dir(project_id) / "CHANGELOG.md"
        if changelog_path.exists():
            entry = f"- **{utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}**: Created experiment {exp.id}: '{exp.title}'.\n"
            with open(changelog_path, "a", encoding="utf-8") as f:
                f.write(entry)

        return exp

    def get_experiment(self, experiment_id: str) -> tuple[Experiment, str]:
        path = self.store.resolve_entity_path(experiment_id)
        if not path.exists():
            raise EntityNotFoundError(f"Experiment {experiment_id} not found.")
        return self.store.load_entity(path, Experiment)

    def list_experiments(self, project_id: str | None = None, status: ExperimentStatus | None = None) -> list[Experiment]:
        results: list[Experiment] = []
        if project_id:
            exp_dir = self.store.get_project_dir(project_id) / "Experiments"
            dirs = [exp_dir] if exp_dir.exists() else []
        else:
            projects_dir = self.vault_root / "00-Projects"
            dirs = [p / "Experiments" for p in projects_dir.iterdir() if (p / "Experiments").exists()] if projects_dir.exists() else []

        for ed in dirs:
            for f in sorted(ed.glob("*.md")):
                try:
                    exp, _ = self.store.load_entity(f, Experiment)
                    if status is None or exp.status == status:
                        results.append(exp)
                except Exception:
                    continue
        return results

    def list_pending_experiments(self, project_id: str | None = None) -> list[Experiment]:
        all_exps = self.list_experiments(project_id=project_id)
        return [e for e in all_exps if e.status not in (ExperimentStatus.COMPLETED, ExperimentStatus.ABANDONED)]

    def validate_preflight(self, experiment_id: str) -> dict[str, Any]:
        exp, _ = self.get_experiment(experiment_id)
        self.validation.validate_experiment_preflight(exp)
        return {"experiment_id": exp.id, "preflight": "passed", "is_exploratory": exp.is_exploratory}

    def update_experiment(
        self,
        experiment_id: str,
        updates: dict[str, Any],
        reason: str | None = None,
        expected_updated_at: datetime | None = None,
    ) -> Experiment:
        exp, body = self.get_experiment(experiment_id)
        orig_params = dict(exp.planned_parameters)
        target_status = updates.get("status")

        # Status transition checks
        if target_status is not None:
            if isinstance(target_status, str):
                target_status = ExperimentStatus(target_status)
            if target_status == ExperimentStatus.READY and exp.status == ExperimentStatus.PLANNED:
                # Preflight check is required before moving to ready!
                self.validation.validate_experiment_preflight(exp)
            self.validation.validate_experiment_transition(exp.status, target_status)
            exp.status = target_status

        # If modifying planned parameters, audit the change
        param_changed = False
        if "planned_parameters" in updates and updates["planned_parameters"] != orig_params:
            param_changed = True
            new_params = updates["planned_parameters"]
            exp.planned_parameters = new_params
            change_note = (
                f"\n\n> [!WARNING] Planned Parameters Modified at {utc_now().isoformat()}\n"
                f"> Reason: {reason or 'No reason provided'}\n"
                f"> Previous: `{orig_params}`\n"
                f"> New: `{new_params}`\n"
            )
            body += change_note

        # Apply other fields
        for field_name, value in updates.items():
            if field_name not in ("status", "planned_parameters", "id", "project_id", "kind"):
                if hasattr(exp, field_name):
                    setattr(exp, field_name, value)

        path = self.store.resolve_entity_path(experiment_id, project_id=exp.project_id)
        self.store.save_entity(exp, body, path=path, expected_updated_at=expected_updated_at)

        # Log change to project CHANGELOG.md
        if param_changed or target_status is not None:
            changelog_path = self.store.get_project_dir(exp.project_id) / "CHANGELOG.md"
            if changelog_path.exists():
                msg = f"- **{utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}**: Updated experiment {exp.id} (Status: {exp.status.value}"
                if reason:
                    msg += f", Reason: {reason}"
                msg += ").\n"
                with open(changelog_path, "a", encoding="utf-8") as f:
                    f.write(msg)

        return exp
