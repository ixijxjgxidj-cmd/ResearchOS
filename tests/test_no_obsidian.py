"""Test I: Complete end-to-end research workflow in an environment without Obsidian."""

from pathlib import Path
from researchos.core.enums import (
    ExperimentOutcome,
    ExperimentStatus,
    PaperReadingStatus,
    RunStatus,
)
from researchos.services.artifact_service import ArtifactService
from researchos.services.context_service import ContextService
from researchos.services.experiment_service import ExperimentService
from researchos.services.handoff_service import HandoffService
from researchos.services.paper_service import PaperService
from researchos.services.project_service import ProjectService
from researchos.services.run_service import RunService


def test_complete_workflow_without_obsidian(tmp_path: Path):
    vault = tmp_path / "standalone_pure_markdown_vault"

    # 1. Initialize vault without Obsidian
    p_svc = ProjectService(vault)
    p_svc.init_vault()

    # 2. Create Project
    proj = p_svc.create_project(
        name="Quantization Aware Training",
        research_question="Can 4-bit INT4 quantization match FP16 perplexity?",
    )

    # 3. Create Paper literature
    pap_svc = PaperService(vault)
    paper = pap_svc.create_paper(
        title="LLM.int8(): 8-bit Matrix Multiplication for Transformers at Scale",
        citekey="dettmers2022llmint8",
        authors=["Tim Dettmers et al."],
        year=2022,
        reading_status=PaperReadingStatus.READ,
        projects=[proj.id],
    )

    # 4. Create Experiment
    e_svc = ExperimentService(vault)
    exp = e_svc.create_experiment(
        project_id=proj.id,
        title="SmoothQuant Calibration on LLaMA-7B",
        hypothesis="Per-channel scaling reduces outlier kurtosis below 3.0.",
        method="Apply per-tensor activation smoothing followed by INT4 weight quantization.",
        literature=[paper.id],
        planned_parameters={"bits": 4, "alpha": 0.5, "calibration_samples": 512},
        expected_result="Perplexity degradation < 0.2 points",
        success_criteria=["Wikitext perplexity <= 5.8"],
    )

    # Preflight check and transition to ready
    e_svc.validate_preflight(exp.id)
    e_svc.update_experiment(exp.id, {"status": ExperimentStatus.READY})

    # 5. Create Run and execute
    r_svc = RunService(vault)
    run = r_svc.create_run(
        experiment_id=exp.id,
        agent_name="standalone_agent",
        executor_type="local",
    )

    # 6. Register Artifact
    metrics_file = vault / "smoothquant_eval.json"
    metrics_file.write_text('{"perplexity": 5.68, "memory_savings_ratio": 0.72}', encoding="utf-8")

    art_svc = ArtifactService(vault)
    art = art_svc.register_artifact(
        run_id=run.id,
        path=str(metrics_file),
        role="metrics",
    )

    # 7. Complete Run
    r_svc.complete_run(
        run_id=run.id,
        status=RunStatus.SUCCEEDED,
        actual_parameters={"bits": 4, "alpha": 0.53, "calibration_samples": 512},
        metrics={"perplexity": 5.68},
        result_summary="INT4 SmoothQuant reached 5.68 perplexity with 72% memory savings.",
        experiment_outcome=ExperimentOutcome.POSITIVE,
    )

    # 8. Update Handoff & Dashboard
    h_svc = HandoffService(vault)
    h_svc.update_handoff(
        project_id=proj.id,
        current_focus="SmoothQuant calibration validated; proceed to kernel acceleration.",
        completed_since_last=[f"Ran experiment {exp.id} and achieved 5.68 perplexity"],
        next_steps=["Benchmark Triton INT4 GEMM kernels"],
    )
    p_svc.generate_dashboards()

    # 9. Build Context Pack
    ctx_svc = ContextService(vault)
    pack = ctx_svc.build_context(exp.id)

    # 10. Assertions: verify pure Markdown files are valid, self-contained, and parseable
    assert (vault / "99-Dashboard" / "Projects.md").exists()
    assert (vault / "99-Dashboard" / "Pending-Experiments.md").exists()
    assert (vault / "99-Dashboard" / "Literature-Overview.md").exists()
    assert (vault / "00-Projects" / proj.id / "STATUS.md").exists()
    assert (vault / "00-Projects" / proj.id / "HANDOFF.md").exists()
    assert "# Research Context Pack:" in pack
    assert "dettmers2022llmint8" in pack
    assert "5.68" in pack
