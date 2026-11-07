"""Run service for tracking execution runs, parameters, and results."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from researchos.core.enums import (
    ExperimentOutcome,
    ExperimentStatus,
    IdPrefix,
    RunStatus,
)
from researchos.core.exceptions import (
    EntityNotFoundError,
    ValidationError,
)
from researchos.core.ids import IdGenerator
from researchos.core.models import (
    Experiment,
    Run,
    utc_now,
)
from researchos.services.validation_service import ValidationService
from researchos.storage.markdown_store import MarkdownStore


class RunService:
    """Manages individual experimental execution runs, parameter isolation, and telemetry."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.store = MarkdownStore(self.vault_root)
        self.id_gen = IdGenerator(self.vault_root)
        self.validation = ValidationService()

    def create_run(
        self,
        experiment_id: str,
        agent_name: str,
        session_id: str | None = None,
        executor_type: str = "local",
        server_id: str | None = None,
        server_task_id: str | None = None,
        infrastructure_provider: str | None = None,
        working_directory: str | None = None,
        actual_parameters: dict[str, Any] | None = None,
        random_seed: int | None = None,
        code_repository: str | None = None,
        code_commit: str | None = None,
        environment: dict[str, Any] | None = None,
    ) -> Run:
        """Initializes a new execution Run linked to an Experiment."""
        exp_path = self.store.resolve_entity_path(experiment_id)
        if not exp_path.exists():
            raise EntityNotFoundError(f"Experiment {experiment_id} not found.")

        exp, exp_body = self.store.load_entity(exp_path, Experiment)

        run_id = self.id_gen.generate_id(IdPrefix.RUN)
        run = Run(
            id=run_id,
            project_id=exp.project_id,
            experiment_id=exp.id,
            status=RunStatus.RUNNING,
            agent_name=agent_name,
            session_id=session_id,
            executor_type=executor_type,
            server_id=server_id,
            server_task_id=server_task_id,
            infrastructure_provider=infrastructure_provider,
            working_directory=working_directory,
            started_at=utc_now(),
            actual_parameters=actual_parameters or {},
            random_seed=random_seed,
            code_repository=code_repository,
            code_commit=code_commit,
            environment=environment or {},
        )

        tpl_path = self.vault_root / "90-Templates" / "run.md"
        body = tpl_path.read_text(encoding="utf-8") if tpl_path.exists() else "# {id} {agent_name} Execution\n\n## Execution Overview\n"
        body = body.replace("{id}", run.id).replace("{agent_name}", run.agent_name)

        run_path = self.store.resolve_entity_path(run.id, project_id=exp.project_id)
        self.store.save_entity(run, body, path=run_path)

        # Update experiment's runs list & set status to running if ready
        if run.id not in exp.runs:
            exp.runs.append(run.id)
        if exp.status in (ExperimentStatus.READY, ExperimentStatus.PLANNED):
            exp.status = ExperimentStatus.RUNNING

        self.store.save_entity(exp, exp_body, path=exp_path)

        # Append to project CHANGELOG.md
        changelog_path = self.store.get_project_dir(exp.project_id) / "CHANGELOG.md"
        if changelog_path.exists():
            entry = f"- **{utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}**: Started run {run.id} by agent '{agent_name}' for {exp.id}.\n"
            with open(changelog_path, "a", encoding="utf-8") as f:
                f.write(entry)

        return run

    def get_run(self, run_id: str) -> tuple[Run, str]:
        path = self.store.resolve_entity_path(run_id)
        if not path.exists():
            raise EntityNotFoundError(f"Run {run_id} not found.")
        return self.store.load_entity(path, Run)

    def list_runs(self, experiment_id: str | None = None, project_id: str | None = None) -> list[Run]:
        results: list[Run] = []
        if project_id:
            runs_dir = self.store.get_project_dir(project_id) / "Runs"
            dirs = [runs_dir] if runs_dir.exists() else []
        else:
            projects_dir = self.vault_root / "00-Projects"
            dirs = [p / "Runs" for p in projects_dir.iterdir() if (p / "Runs").exists()] if projects_dir.exists() else []

        for rd in dirs:
            for f in sorted(rd.glob("*.md")):
                try:
                    r, _ = self.store.load_entity(f, Run)
                    if experiment_id is None or r.experiment_id == experiment_id:
                        results.append(r)
                except Exception:
                    continue
        return results

    def update_run(self, run_id: str, updates: dict[str, Any]) -> Run:
        run, body = self.get_run(run_id)
        for k, v in updates.items():
            if k not in ("id", "project_id", "experiment_id", "kind") and hasattr(run, k):
                setattr(run, k, v)
        path = self.store.resolve_entity_path(run_id, project_id=run.project_id)
        self.store.save_entity(run, body, path=path)
        return run

    def complete_run(
        self,
        run_id: str,
        status: RunStatus,
        actual_parameters: dict[str, Any],
        metrics: dict[str, Any] | None = None,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
        deviations: list[str] | None = None,
        result_summary: str | None = None,
        experiment_outcome: ExperimentOutcome | None = None,
    ) -> Run:
        """Completes an experimental run, records telemetry, and propagates findings to Experiment."""
        run, body = self.get_run(run_id)

        # Validate lifecycle transition
        self.validation.validate_run_transition(run.status, status)

        run.status = status
        run.finished_at = utc_now()
        run.actual_parameters = actual_parameters or run.actual_parameters
        if metrics:
            run.metrics = metrics
        if errors:
            run.errors = errors
        if warnings:
            run.warnings = warnings
        if deviations:
            run.deviations = deviations
        if result_summary:
            run.result_summary = result_summary

        # Append execution summary to Run body
        summary_block = (
            f"\n\n## Completion Summary\n"
            f"- **Finished At**: {run.finished_at.isoformat()}\n"
            f"- **Status**: `{run.status.value}`\n"
            f"- **Summary**: {result_summary or 'Completed.'}\n"
        )
        if metrics:
            summary_block += f"- **Metrics**: `{metrics}`\n"
        if deviations:
            summary_block += f"- **Deviations**: {deviations}\n"
        if errors:
            summary_block += f"- **Errors**: {errors}\n"

        body += summary_block

        run_path = self.store.resolve_entity_path(run.id, project_id=run.project_id)
        self.store.save_entity(run, body, path=run_path)

        # Backfill and update parent Experiment
        exp_path = self.store.resolve_entity_path(run.experiment_id, project_id=run.project_id)
        if exp_path.exists():
            exp, exp_body = self.store.load_entity(exp_path, Experiment)

            # Move experiment to needs_review upon run completion
            exp.status = ExperimentStatus.NEEDS_REVIEW
            if experiment_outcome:
                exp.outcome = experiment_outcome
            elif status == RunStatus.FAILED and exp.outcome == ExperimentOutcome.PENDING:
                # Mark as execution failure, NOT negative scientific outcome
                exp.outcome = ExperimentOutcome.FAILED

            # Backfill actual results and deviations into Experiment body
            exp_body += (
                f"\n\n### Run {run.id} Output ({status.value})\n"
                f"- **Agent**: {run.agent_name}\n"
                f"- **Result Summary**: {result_summary or 'No summary provided'}\n"
                f"- **Actual Parameters**: `{actual_parameters}`\n"
                f"- **Metrics**: `{metrics or {}}`\n"
            )
            if deviations:
                exp_body += f"- **Deviations**: {', '.join(deviations)}\n"

            self.store.save_entity(exp, exp_body, path=exp_path)

        # CHANGELOG entry
        changelog_path = self.store.get_project_dir(run.project_id) / "CHANGELOG.md"
        if changelog_path.exists():
            msg = f"- **{utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}**: Run {run.id} completed with status '{status.value}'.\n"
            with open(changelog_path, "a", encoding="utf-8") as f:
                f.write(msg)

        return run
