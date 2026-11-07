"""Tests for ResearchOS Audit engine."""

from pathlib import Path
from researchos.core.enums import (
    ClaimStatus,
    ExperimentOutcome,
)
from researchos.services.audit_service import AuditService
from researchos.services.claim_service import ClaimService
from researchos.services.experiment_service import ExperimentService
from researchos.services.project_service import ProjectService


def test_audit_detects_unverified_claims_and_negative_results(
    vault_dir: Path,
    project_service: ProjectService,
    experiment_service: ExperimentService,
    claim_service: ClaimService,
    audit_service: AuditService,
):
    proj = project_service.create_project(name="Audit Target Project")

    # Experiment with negative outcome
    exp = experiment_service.create_experiment(
        project_id=proj.id,
        title="Negative Outcome Experiment",
        is_exploratory=True,
    )
    experiment_service.update_experiment(exp.id, {"outcome": ExperimentOutcome.NEGATIVE})

    # Unverified claim falsely marked as supported without any evidence
    claim = claim_service.create_claim(
        project_id=proj.id,
        text="Novel architecture achieves 99.9% accuracy.",
        status=ClaimStatus.SUPPORTED,
        supporting_experiments=[],  # Empty!
    )

    # Run audit
    report = audit_service.run_audit(proj.id)

    assert report["status"] == "failed"
    assert report["errors"] > 0
    issues = report["issues"]

    # Must catch the unbacked supported claim
    assert any("Claim marked 'supported' without any supporting experiments" in i["message"] for i in issues)

    # Must note the negative outcome preservation notice
    assert any("Negative outcome" in i["message"] for i in issues)
