"""Validation service for lifecycle transitions, preflight checks, and reference integrity."""

from researchos.core.enums import (
    ExperimentOutcome,
    ExperimentStatus,
    RunStatus,
)
from researchos.core.exceptions import (
    InvalidStateTransitionError,
    PreflightCheckError,
    ValidationError,
)
from researchos.core.models import Experiment, Run

VALID_EXPERIMENT_TRANSITIONS: dict[ExperimentStatus, set[ExperimentStatus]] = {
    ExperimentStatus.PLANNED: {ExperimentStatus.READY, ExperimentStatus.ABANDONED},
    ExperimentStatus.READY: {ExperimentStatus.RUNNING, ExperimentStatus.BLOCKED, ExperimentStatus.ABANDONED},
    ExperimentStatus.RUNNING: {ExperimentStatus.NEEDS_REVIEW, ExperimentStatus.BLOCKED, ExperimentStatus.ABANDONED},
    ExperimentStatus.BLOCKED: {ExperimentStatus.READY, ExperimentStatus.RUNNING, ExperimentStatus.ABANDONED},
    ExperimentStatus.NEEDS_REVIEW: {ExperimentStatus.COMPLETED, ExperimentStatus.READY, ExperimentStatus.ABANDONED},
    ExperimentStatus.COMPLETED: set(),
    ExperimentStatus.ABANDONED: set(),
}

VALID_RUN_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.CREATED: {RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.CANCELLED},
    RunStatus.QUEUED: {RunStatus.RUNNING, RunStatus.CANCELLED},
    RunStatus.RUNNING: {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.INTERRUPTED, RunStatus.NEEDS_REVIEW},
    RunStatus.SUCCEEDED: {RunStatus.NEEDS_REVIEW, RunStatus.REVIEWED},
    RunStatus.FAILED: {RunStatus.NEEDS_REVIEW, RunStatus.REVIEWED},
    RunStatus.INTERRUPTED: {RunStatus.NEEDS_REVIEW, RunStatus.RUNNING, RunStatus.CANCELLED},
    RunStatus.NEEDS_REVIEW: {RunStatus.REVIEWED},
    RunStatus.CANCELLED: set(),
    RunStatus.REVIEWED: set(),
}


class ValidationService:
    """Enforces scientific workflow rules and prevents invalid mutations."""

    @staticmethod
    def validate_experiment_transition(current: ExperimentStatus, target: ExperimentStatus) -> None:
        if current == target:
            return
        allowed = VALID_EXPERIMENT_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise InvalidStateTransitionError(
                f"Invalid experiment transition from '{current}' to '{target}'. "
                f"Allowed target states: {[s.value for s in allowed]}."
            )

    @staticmethod
    def validate_run_transition(current: RunStatus, target: RunStatus) -> None:
        if current == target:
            return
        allowed = VALID_RUN_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise InvalidStateTransitionError(
                f"Invalid run transition from '{current}' to '{target}'. "
                f"Allowed target states: {[s.value for s in allowed]}."
            )

    @staticmethod
    def validate_experiment_preflight(exp: Experiment) -> list[str]:
        """Checks if an experiment is mature enough to move from 'planned' to 'ready'.

        Raises PreflightCheckError if missing critical elements and not marked exploratory.
        """
        errors: list[str] = []

        if not exp.objective and not exp.research_question:
            errors.append("Experiment must specify either 'objective' or 'research_question'.")

        if not exp.is_exploratory:
            if not exp.hypothesis:
                errors.append("Non-exploratory experiment must specify 'hypothesis'.")
            if not exp.method:
                errors.append("Non-exploratory experiment must specify 'method'.")
            if not exp.success_criteria:
                errors.append("Non-exploratory experiment must define at least one 'success_criteria'.")
            if not exp.planned_parameters:
                errors.append("Non-exploratory experiment must define 'planned_parameters'.")

        if errors:
            raise PreflightCheckError(
                f"Preflight checks failed for experiment {exp.id}:\n" + "\n".join(f"- {e}" for e in errors)
            )
        return errors

    @staticmethod
    def validate_run_completion(run: Run, actual_params: dict | None) -> None:
        """Validates that a Run completion records distinct actual execution parameters."""
        if actual_params is None and not run.actual_parameters:
            raise ValidationError(
                f"Run {run.id} cannot be marked complete without recording 'actual_parameters'. "
                "Actual execution parameters must not be omitted."
            )
