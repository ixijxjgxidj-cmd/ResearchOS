"""Tests for Run execution, parameter segregation, failure handling, and negative outcomes."""

from pathlib import Path
from researchos.core.enums import (
    ExperimentOutcome,
    ExperimentStatus,
    RunStatus,
)
from researchos.services.experiment_service import ExperimentService
from researchos.services.project_service import ProjectService
from researchos.services.run_service import RunService


def test_run_success_and_parameter_segregation(
    vault_dir: Path,
    project_service: ProjectService,
    experiment_service: ExperimentService,
    run_service: RunService,
):
    proj = project_service.create_project(name="Diffusion Training")
    exp = experiment_service.create_experiment(
        project_id=proj.id,
        title="DDPM on CelebA 64x64",
        is_exploratory=True,
        planned_parameters={"learning_rate": 1e-4, "timesteps": 1000},
    )

    # Agent A launches Run
    run = run_service.create_run(
        experiment_id=exp.id,
        agent_name="claude-code",
        executor_type="local",
    )
    assert run.status == RunStatus.RUNNING

    # Parent experiment status automatically moved to running
    exp_after_start, _ = experiment_service.get_experiment(exp.id)
    assert exp_after_start.status == ExperimentStatus.RUNNING

    # Complete run with DIFFERENT actual parameters
    actual_params = {"learning_rate": 2e-4, "timesteps": 800, "actual_batch_size": 32}
    metrics = {"fid_score": 12.4, "train_loss": 0.021}
    completed_run = run_service.complete_run(
        run_id=run.id,
        status=RunStatus.SUCCEEDED,
        actual_parameters=actual_params,
        metrics=metrics,
        result_summary="Completed 100 epochs, FID converged cleanly.",
        experiment_outcome=ExperimentOutcome.POSITIVE,
    )

    assert completed_run.status == RunStatus.SUCCEEDED
    assert completed_run.actual_parameters != exp.planned_parameters
    assert completed_run.metrics["fid_score"] == 12.4

    # Parent experiment moves to needs_review with backfilled actual results
    exp_finished, exp_body = experiment_service.get_experiment(exp.id)
    assert exp_finished.status == ExperimentStatus.NEEDS_REVIEW
    assert exp_finished.outcome == ExperimentOutcome.POSITIVE
    assert "fid_score" in exp_body
    assert run.id in exp_finished.runs


def test_failed_run_preservation_and_outcome_distinction(
    vault_dir: Path,
    project_service: ProjectService,
    experiment_service: ExperimentService,
    run_service: RunService,
):
    """Test E: Execution failure must be preserved and not marked as negative scientific outcome."""
    proj = project_service.create_project(name="Transformer Scaling")
    exp = experiment_service.create_experiment(
        project_id=proj.id,
        title="Training 70B parameter model",
        is_exploratory=True,
    )

    run = run_service.create_run(
        experiment_id=exp.id,
        agent_name="codex-worker",
    )

    # Simulate CUDA OOM crash
    run_service.complete_run(
        run_id=run.id,
        status=RunStatus.FAILED,
        actual_parameters={"world_size": 8, "batch_size": 512},
        errors=["CUDA out of memory: tried to allocate 24GB on GPU 0"],
        result_summary="Process killed by OOM killer during step 120.",
    )

    r_failed, r_body = run_service.get_run(run.id)
    assert r_failed.status == RunStatus.FAILED
    assert "CUDA out of memory" in r_body

    # Experiment outcome must be FAILED, NOT NEGATIVE
    exp_state, _ = experiment_service.get_experiment(exp.id)
    assert exp_state.outcome == ExperimentOutcome.FAILED
    assert exp_state.outcome != ExperimentOutcome.NEGATIVE
    assert exp_state.status == ExperimentStatus.NEEDS_REVIEW
