"""Tests for Artifact registration, SHA-256 hashing, and integrity verification."""

from pathlib import Path
from researchos.core.enums import ArtifactRole
from researchos.services.artifact_service import ArtifactService
from researchos.services.experiment_service import ExperimentService
from researchos.services.project_service import ProjectService
from researchos.services.run_service import RunService


def test_artifact_registration_and_integrity(
    vault_dir: Path,
    project_service: ProjectService,
    experiment_service: ExperimentService,
    run_service: RunService,
    artifact_service: ArtifactService,
):
    proj = project_service.create_project(name="Model Checkpoint Project")
    exp = experiment_service.create_experiment(
        project_id=proj.id,
        title="Artifact Generation Experiment",
        is_exploratory=True,
    )
    run = run_service.create_run(experiment_id=exp.id, agent_name="trainer")

    # Create dummy artifact file on disk
    weights_file = vault_dir / "model_epoch10.bin"
    weights_file.write_bytes(b"\x00\x01\x02\x03FAKE_MODEL_WEIGHTS_42\xfe\xff")

    # Register artifact
    art = artifact_service.register_artifact(
        run_id=run.id,
        path=str(weights_file),
        role=ArtifactRole.CHECKPOINT,
        name="best_weights.bin",
    )

    assert art.id.startswith("ART-")
    assert art.size_bytes == weights_file.stat().st_size
    assert len(art.sha256) == 64
    assert art.immutable is True

    # Verify initial valid state
    v_result = artifact_service.verify_artifact(art.id)
    assert v_result["status"] == "valid"
    assert v_result["match"] is True

    # Modify the physical file to simulate corruption/tampering
    weights_file.write_bytes(b"CORRUPTED_MODIFIED_CONTENT")

    # Verification must detect corruption and hash mismatch
    v_corrupt = artifact_service.verify_artifact(art.id)
    assert v_corrupt["status"] == "corrupted"
    assert v_corrupt["match"] is False
    assert v_corrupt["current_sha256"] != art.sha256
