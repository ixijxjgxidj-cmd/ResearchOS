"""Tests for Three-Level Retrieval Modes (quick, task, paper, full)."""

from pathlib import Path
import pytest

from researchos.core.context_builder import ContextBuilder
from researchos.core.memory_service import MemoryService
from researchos.core.project_service import ProjectService
from researchos.models.memory import MemoryType


@pytest.fixture
def retrieval_project(tmp_path: Path):
    vault_dir = tmp_path / "ResearchVault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    ps = ProjectService(vault_dir)
    ms = MemoryService(vault_dir)
    cb = ContextBuilder(vault_dir)

    # Create project
    ps.create_project(
        name="Latent Masking Seismic",
        project_id="seismic-ssl",
        research_goal="Unsupervised pretraining on seismic traces using masked autoencoders",
    )

    # Add various types of memories
    ms.add_memory(
        project_id="seismic-ssl",
        type=MemoryType.DECISION,
        title="Use ViT-Patch16 Architecture",
        content="We selected ViT-Patch16 due to linear scaling with trace length.",
        source_agent="Agent-Arch",
        tags=["architecture", "vit"],
    )

    ms.add_memory(
        project_id="seismic-ssl",
        type=MemoryType.OBSERVATION,
        title="Baseline SNR Result",
        content="Observed 14.2 dB SNR improvement on synthetic test set.",
        source_agent="Agent-Eval",
        tags=["experiment", "metrics"],
        experiment_id="EXP-101",
        paper_section="experiments",
        metrics_summary="SNR=+14.2dB, MSE=0.012",
        source_ref="runs/exp101_baseline.pt",
    )

    ms.add_memory(
        project_id="seismic-ssl",
        type=MemoryType.HYPOTHESIS,
        title="Fourier Attention May Reduce Ringing",
        content="Hypothesis: 2D Fourier phase embedding will remove spatial ringing artifacts.",
        source_agent="Agent-Theory",
        tags=["hypothesis", "fourier"],
        paper_section="methodology",
    )

    ms.add_memory(
        project_id="seismic-ssl",
        type=MemoryType.NEGATIVE,
        title="High Mask Ratio Collapses Latent Space",
        content="Mask ratio above 0.85 leads to complete representation collapse.",
        source_agent="Agent-Train",
        tags=["negative", "failure"],
        experiment_id="EXP-102",
        paper_section="ablations",
        metrics_summary="Loss=NaN, collapsed=True",
    )

    return {
        "vault_dir": vault_dir,
        "cb": cb,
        "project_id": "seismic-ssl",
    }


def test_quick_mode_returns_strictly_l0(retrieval_project):
    cb: ContextBuilder = retrieval_project["cb"]
    pid = retrieval_project["project_id"]

    text, meta = cb.build_context_pack(project_id=pid, context_mode="quick")

    assert meta.context_mode == "quick"
    assert meta.included_chunks_count == 1
    assert "Always-on Project Memory" in text
    assert "# MEMORY" in text
    assert "STABLE MEMORY" in text

    # Quick mode must omit L1 and L2 files
    assert "PROJECT.md`" not in text
    assert "STATE.md`" not in text
    assert "HANDOFF.md`" not in text
    assert "due to linear scaling with trace length" not in text
    assert "14.2 dB SNR improvement" not in text
    assert meta.used_tokens < 1000


def test_task_mode_retrieves_l0_and_bm25_matches(retrieval_project):
    cb: ContextBuilder = retrieval_project["cb"]
    pid = retrieval_project["project_id"]

    text, meta = cb.build_context_pack(
        project_id=pid,
        context_mode="task",
        task="Evaluate SNR and synthetic test metrics",
    )

    assert meta.context_mode == "task"
    assert meta.included_chunks_count > 1
    # Contains L0
    assert "Always-on Project Memory" in text
    # Contains L1
    assert "Current Research State" in text
    # Contains matched L2 observation
    assert "Baseline SNR Result" in text
    assert "14.2 dB SNR" in text
    # Contains negative pitfall
    assert "Negative Pitfall" in text


def test_paper_mode_structures_evidence_and_disclaimers(retrieval_project):
    cb: ContextBuilder = retrieval_project["cb"]
    pid = retrieval_project["project_id"]

    text, meta = cb.build_context_pack(project_id=pid, context_mode="paper")

    assert meta.context_mode == "paper"
    # Verifies evidence metadata fields
    assert "Evidence ID" in text
    assert "Experiment ID" in text
    assert "EXP-101" in text
    assert "runs/exp101_baseline.pt" in text
    assert "SNR=+14.2dB" in text

    # Hypotheses must have explicit disclaimer
    assert "[Hypothesis - Unverified Claim; Not Established Empirical Finding]" in text


def test_paper_mode_section_filtering(retrieval_project):
    cb: ContextBuilder = retrieval_project["cb"]
    pid = retrieval_project["project_id"]

    # Filter by 'experiments' section
    text_exp, meta_exp = cb.build_context_pack(
        project_id=pid,
        context_mode="paper",
        paper_section="experiments",
    )

    assert "Baseline SNR Result" in text_exp
    assert "EXP-101" in text_exp

    # Filter by 'methodology' section
    text_meth, meta_meth = cb.build_context_pack(
        project_id=pid,
        context_mode="paper",
        paper_section="methodology",
    )

    assert "Fourier Attention May Reduce Ringing" in text_meth
    assert "EXP-101" not in text_meth


def test_full_mode_includes_all_records(retrieval_project):
    cb: ContextBuilder = retrieval_project["cb"]
    pid = retrieval_project["project_id"]

    text, meta = cb.build_context_pack(project_id=pid, context_mode="full")

    assert meta.context_mode == "full"
    assert "Always-on Project Memory" in text
    assert "Project Overview" in text
    assert "Current Research State" in text
    assert "ViT-Patch16 Architecture" in text
    assert "Baseline SNR Result" in text
    assert "Fourier Attention" in text
    assert "High Mask Ratio Collapses" in text
