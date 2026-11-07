"""Test C: Multi-Agent Context Re-hydration without Chat History."""

from pathlib import Path
from researchos.core.enums import PaperReadingStatus
from researchos.services.context_service import ContextService
from researchos.services.experiment_service import ExperimentService
from researchos.services.handoff_service import HandoffService
from researchos.services.paper_service import PaperService
from researchos.services.project_service import ProjectService


def test_cross_agent_context_recovery(vault_dir: Path):
    # =========================================================================
    # STEP 1: Agent A (e.g. Claude Code) creates project, literature, experiment
    # =========================================================================
    p_svc_a = ProjectService(vault_dir)
    e_svc_a = ExperimentService(vault_dir)
    pap_svc_a = PaperService(vault_dir)
    h_svc_a = HandoffService(vault_dir)

    proj = p_svc_a.create_project(
        name="Sparse Autoencoder Interpretability",
        research_question="Can sparse autoencoders extract monosemantic features from residual stream layer 8?",
        objectives=["Train SAE with L1 penalty", "Evaluate feature sparsity and interpretability score"],
    )

    paper = pap_svc_a.create_paper(
        title="Towards Monosemanticity: Decomposing Language Models With Dictionary Learning",
        citekey="bricken2023towards",
        authors=["Bricken et al."],
        year=2023,
        abstract="We decompose language model activations into interpretable features using sparse autoencoders.",
        reading_status=PaperReadingStatus.SYNTHESIZED,
        projects=[proj.id],
    )

    exp = e_svc_a.create_experiment(
        project_id=proj.id,
        title="SAE L1 Lambda Grid Search",
        hypothesis="L1 penalty lambda=0.01 provides optimal Pareto trade-off between loss and dead neurons (<5%).",
        method="Train 16k latent dictionary on 10M tokens using Adam optimizer.",
        literature=[paper.id],
        planned_parameters={"lambda": 0.01, "dictionary_size": 16384, "batch_size": 2048},
        expected_result="Dead feature count < 5%, reconstruction MSE < 0.05",
        success_criteria=["Reconstruction loss delta < 5%", "Dead latents < 5%"],
    )

    # Agent A updates handoff and terminates session
    h_svc_a.update_handoff(
        project_id=proj.id,
        current_focus="Completed mathematical specification of SAE objective; ready for training execution.",
        completed_since_last=["Literature review of Bricken et al.", f"Designed experiment {exp.id}"],
        modified_files=[f"00-Projects/{proj.id}/Experiments/{exp.id}.md", f"01-Literature/{paper.id}.md"],
        open_issues=["Need GPU with >= 40GB VRAM to run dictionary training efficiently."],
        next_steps=[f"Agent B: Run preflight on {exp.id}", "Claim GPU node via DSH", f"Execute Run for {exp.id}"],
        target_files_for_next_agent=[f"00-Projects/{proj.id}/Experiments/{exp.id}.md"],
    )

    # Agent A's memory / session is completely purged
    del p_svc_a, e_svc_a, pap_svc_a, h_svc_a

    # =========================================================================
    # STEP 2: Agent B (e.g. Codex) starts a brand-new independent session
    # Agent B has ZERO chat history or memory from Agent A.
    # Agent B only has access to ResearchOS Context Builder!
    # =========================================================================
    ctx_svc_b = ContextService(vault_dir)

    # Agent B builds context for target experiment
    context_pack_md = ctx_svc_b.build_context(exp.id)

    # Assertions: Verify Agent B recovers all critical scientific facts without conversation history
    assert "# Research Context Pack:" in context_pack_md
    assert proj.id in context_pack_md
    assert "Sparse Autoencoder Interpretability" in context_pack_md
    assert "residual stream layer 8" in context_pack_md
    assert exp.id in context_pack_md
    assert "SAE L1 Lambda Grid Search" in context_pack_md
    assert "L1 penalty lambda=0.01" in context_pack_md
    assert "16384" in context_pack_md
    assert "Bricken et al." in context_pack_md
    assert "bricken2023towards" in context_pack_md
    assert "Need GPU with >= 40GB VRAM" in context_pack_md
    assert "Agent B: Run preflight" in context_pack_md
    assert f"00-Projects/{proj.id}/PROJECT.md" in context_pack_md
    assert f"01-Literature/{paper.id}.md" in context_pack_md
