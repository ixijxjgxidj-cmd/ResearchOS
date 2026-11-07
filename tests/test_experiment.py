"""Tests for Experiment lifecycle, preflight checks, and parameter management."""

import pytest
from pathlib import Path
from researchos.core.enums import (
    ExperimentOutcome,
    ExperimentStatus,
)
from researchos.core.exceptions import (
    InvalidStateTransitionError,
    PreflightCheckError,
)
from researchos.services.experiment_service import ExperimentService
from researchos.services.project_service import ProjectService


def test_experiment_lifecycle_and_preflight(
    vault_dir: Path,
    project_service: ProjectService,
    experiment_service: ExperimentService,
):
    # 1. Setup project
    proj = project_service.create_project(name="Adversarial Attack Baseline")

    # 2. Create planned experiment with missing hypothesis/method (non-exploratory)
    exp = experiment_service.create_experiment(
        project_id=proj.id,
        title="PGD Attack on ResNet-18",
        objective="Assess baseline error rate under 8/255 perturbation",
        is_exploratory=False,
    )
    assert exp.status == ExperimentStatus.PLANNED
    assert exp.outcome == ExperimentOutcome.PENDING

    # 3. Preflight check must fail because non-exploratory experiment lacks hypothesis, method, success_criteria, params
    with pytest.raises(PreflightCheckError):
        experiment_service.validate_preflight(exp.id)

    # 4. Attempting to transition to ready before passing preflight must fail
    with pytest.raises(PreflightCheckError):
        experiment_service.update_experiment(exp.id, {"status": ExperimentStatus.READY})

    # 5. Populate required scientific fields
    experiment_service.update_experiment(
        exp.id,
        {
            "hypothesis": "ResNet-18 accuracy drops below 20% under 20-step PGD with epsilon=8/255.",
            "method": "Execute 20 iterations of PGD with step size 2/255 on test set.",
            "planned_parameters": {"epsilon": 0.03137, "steps": 20, "step_size": 0.00784, "batch_size": 128},
            "success_criteria": ["Attack converges", "Robust accuracy computed"],
        },
    )

    # 6. Now preflight passes
    res = experiment_service.validate_preflight(exp.id)
    assert res["preflight"] == "passed"

    # 7. Transition to ready
    ready_exp = experiment_service.update_experiment(exp.id, {"status": ExperimentStatus.READY})
    assert ready_exp.status == ExperimentStatus.READY

    # 8. Modifying planned parameters logs deviation and warning in markdown body
    updated_exp = experiment_service.update_experiment(
        exp.id,
        {"planned_parameters": {"epsilon": 0.0627, "steps": 40, "batch_size": 64}},
        reason="Exploring stronger perturbation bound",
    )
    assert updated_exp.planned_parameters["steps"] == 40

    _, body = experiment_service.get_experiment(exp.id)
    assert "Planned Parameters Modified" in body
    assert "Exploring stronger perturbation bound" in body
