"""Script to generate a realistic example ResearchVault."""

from pathlib import Path
import shutil
import json

from researchos.core.enums import (
    ClaimStatus,
    ExperimentOutcome,
    PaperReadingStatus,
    RunStatus,
)
from researchos.services.artifact_service import ArtifactService
from researchos.services.claim_service import ClaimService
from researchos.services.experiment_service import ExperimentService
from researchos.services.finding_service import FindingService
from researchos.services.handoff_service import HandoffService
from researchos.services.paper_service import PaperService
from researchos.services.project_service import ProjectService
from researchos.services.run_service import RunService


def main() -> None:
    vault_dir = Path("examples/example-vault")
    if vault_dir.exists():
        shutil.rmtree(vault_dir)

    p_svc = ProjectService(vault_dir)
    p_svc.init_vault()

    # Copy root AGENTS.md to vault root
    shutil.copy2("AGENTS.md", vault_dir / "AGENTS.md")

    # 1. Create Project
    proj = p_svc.create_project(
        name="Deep Residual Scaling Laws",
        research_question="How does transformer layer width vs depth scale when parameter budget is held constant at 7B?",
        objectives=[
            "Train grid of 12 distinct aspect-ratio models",
            "Compute Chinchilla-optimal compute frontiers",
        ],
    )

    # 2. Create Paper
    pap_svc = PaperService(vault_dir)
    paper = pap_svc.create_paper(
        title="Training Compute-Optimal Large Language Models",
        citekey="hoffmann2022chinchilla",
        authors=["Jordan Hoffmann", "Sebastian Borgeaud", "Arthur Mensch"],
        year=2022,
        abstract="We investigate the optimal model size and number of tokens for training a transformer under a compute budget.",
        reading_status=PaperReadingStatus.SYNTHESIZED,
        projects=[proj.id],
    )

    # 3. Create Experiment
    e_svc = ExperimentService(vault_dir)
    exp = e_svc.create_experiment(
        project_id=proj.id,
        title="Depth-to-Width Ratio Comparison at 100B Tokens",
        hypothesis="Aspect ratio depth/width between 0.8 and 1.2 minimizes validation perplexity on pretraining corpora.",
        method="Pretrain 7B models on 100B tokens using FlashAttention-2 with cosine decay schedule.",
        literature=[paper.id],
        planned_parameters={"tokens": "100B", "batch_size": 1024, "learning_rate": 3e-4, "seq_len": 4096},
        expected_result="Validation loss lowest for 32-layer 4096-width configuration.",
        success_criteria=["Training stability without gradient spikes", "Validation perplexity <= 8.5"],
    )

    # Preflight & Ready
    e_svc.validate_preflight(exp.id)
    e_svc.update_experiment(exp.id, {"status": "ready"})

    # 4. Create Run
    r_svc = RunService(vault_dir)
    run = r_svc.create_run(
        experiment_id=exp.id,
        agent_name="claude-code",
        executor_type="dsh",
        server_id="srv_a100_node04",
        working_directory="~/workspace/depth_width_exp001_claude_20261107",
        environment={"cuda": "12.4", "framework": "pytorch-2.4"},
    )

    # 5. Create Artifact
    dummy_metrics = vault_dir / "eval_perplexity_log.json"
    dummy_metrics.write_text(
        json.dumps({"val_loss": 1.98, "perplexity": 7.24, "tokens_processed": 100_000_000_000}),
        encoding="utf-8",
    )

    art_svc = ArtifactService(vault_dir)
    art = art_svc.register_artifact(
        run_id=run.id,
        path=str(dummy_metrics),
        role="metrics",
        name="final_evaluation_metrics.json",
    )

    # 6. Complete Run
    r_svc.complete_run(
        run_id=run.id,
        status=RunStatus.SUCCEEDED,
        actual_parameters={
            "tokens": "100B",
            "batch_size": 1024,
            "learning_rate": 3e-4,
            "seq_len": 4096,
            "grad_clip": 1.0,
        },
        metrics={"val_loss": 1.98, "perplexity": 7.24},
        result_summary="Pretraining reached 100B tokens with validation perplexity 7.24.",
        experiment_outcome=ExperimentOutcome.POSITIVE,
    )

    # 7. Create Finding
    find_svc = FindingService(vault_dir)
    find_svc.create_finding(
        project_id=proj.id,
        experiment_id=exp.id,
        run_id=run.id,
        title="Aspect ratio 1.0 yields lowest perplexity under constant 7B compute budget.",
        summary="Models with depth 32 and width 4096 outperformed narrower 48-layer or wider 20-layer counterparts by 0.3 PPL.",
        evidence_artifacts=[art.id],
        literature=[paper.id],
    )

    # 8. Create Claim
    claim_svc = ClaimService(vault_dir)
    claim_svc.create_claim(
        project_id=proj.id,
        text="Near-unity aspect ratios (depth/width ≈ 1.0) optimize token efficiency for 7B parameter dense transformers.",
        status=ClaimStatus.SUPPORTED,
        supporting_experiments=[exp.id],
        supporting_runs=[run.id],
        literature=[paper.id],
        artifacts=[art.id],
        limitations=["Evaluated only up to 100B tokens; asymptotic behavior at 1T+ tokens remains open."],
        manuscript_section="Section 5: Optimal Aspect Ratio Scaling",
    )

    # 9. Update Handoff & Dashboard
    h_svc = HandoffService(vault_dir)
    h_svc.update_handoff(
        project_id=proj.id,
        current_focus="100B token pretraining baseline complete; ready for manuscript draft.",
        completed_since_last=[
            "Pretrained 32L-4096W configuration",
            "Extracted finding FIND-2026-001",
        ],
        next_steps=["Agent C: Draft Section 5 of manuscript citing Claim CLAIM-2026-001"],
    )

    p_svc.generate_dashboards()
    print("Example ResearchVault generated successfully at", vault_dir)


if __name__ == "__main__":
    main()
