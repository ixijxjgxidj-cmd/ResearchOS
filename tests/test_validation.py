"""Tests for lifecycle state machine and validation rules."""

import pytest
from researchos.core.enums import ExperimentStatus, RunStatus
from researchos.core.exceptions import InvalidStateTransitionError
from researchos.services.validation_service import ValidationService


def test_experiment_transitions():
    v = ValidationService()

    # Valid transitions
    v.validate_experiment_transition(ExperimentStatus.PLANNED, ExperimentStatus.READY)
    v.validate_experiment_transition(ExperimentStatus.READY, ExperimentStatus.RUNNING)
    v.validate_experiment_transition(ExperimentStatus.RUNNING, ExperimentStatus.NEEDS_REVIEW)
    v.validate_experiment_transition(ExperimentStatus.NEEDS_REVIEW, ExperimentStatus.COMPLETED)

    # Invalid jump: planned -> completed
    with pytest.raises(InvalidStateTransitionError):
        v.validate_experiment_transition(ExperimentStatus.PLANNED, ExperimentStatus.COMPLETED)

    # Invalid jump: running -> ready
    with pytest.raises(InvalidStateTransitionError):
        v.validate_experiment_transition(ExperimentStatus.RUNNING, ExperimentStatus.READY)


def test_run_transitions():
    v = ValidationService()

    # Valid transitions
    v.validate_run_transition(RunStatus.CREATED, RunStatus.RUNNING)
    v.validate_run_transition(RunStatus.RUNNING, RunStatus.SUCCEEDED)
    v.validate_run_transition(RunStatus.SUCCEEDED, RunStatus.NEEDS_REVIEW)

    # Invalid jump: created -> completed directly without running
    with pytest.raises(InvalidStateTransitionError):
        v.validate_run_transition(RunStatus.CREATED, RunStatus.REVIEWED)
