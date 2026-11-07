"""Test: Complete end-to-end research workflow in an environment without Obsidian."""

from pathlib import Path

from researchos.core.context_builder import ContextBuilder
from researchos.core.handoff_service import HandoffService
from researchos.core.memory_service import MemoryService
from researchos.core.project_service import ProjectService
from researchos.models.memory import MemoryType


def test_complete_workflow_without_obsidian(tmp_path: Path):
    vault = tmp_path / "standalone_pure_markdown_vault"

    # 1. Initialize project without Obsidian
    p_svc = ProjectService(vault)
    proj = p_svc.create_project(
        name="Quantization Aware Training",
        project_id="qat-study",
        research_goal="Can 4-bit INT4 quantization match FP16 perplexity?",
    )
    p_dir = Path(proj.project_dir)

    # 2. Add Literature Reference
    m_svc = MemoryService(vault)
    ref_mem = m_svc.add_memory(
        project_id="qat-study",
        type=MemoryType.REFERENCE,
        title="LLM.int8(): 8-bit Matrix Multiplication for Transformers at Scale",
        content="Paper DOI: 10.48550/arXiv.2208.07339. Authors: Tim Dettmers et al. (2022).",
        tags=["literature", "quantization"],
        source_ref="arXiv:2208.07339",
    )

    # 3. Add Working Hypothesis
    hyp_mem = m_svc.add_memory(
        project_id="qat-study",
        type=MemoryType.HYPOTHESIS,
        title="SmoothQuant Calibration Hypothesis",
        content="Per-channel scaling reduces outlier kurtosis below 3.0, preserving perplexity within 0.2 points of FP16.",
        related_memory_ids=[ref_mem.id],
    )

    # 4. Add Empirical Observation
    obs_mem = m_svc.add_memory(
        project_id="qat-study",
        type=MemoryType.OBSERVATION,
        title="SmoothQuant Calibration on LLaMA-7B",
        content="Per-tensor activation smoothing followed by INT4 weight quantization achieved 5.68 perplexity with 72% memory savings.",
        tags=["benchmark", "positive"],
        related_memory_ids=[hyp_mem.id],
        confidence=0.95,
    )

    # 5. Add Negative Experience
    neg_mem = m_svc.add_memory(
        project_id="qat-study",
        type=MemoryType.NEGATIVE,
        title="Static Per-Tensor Quantization Failure",
        content="Static per-tensor INT4 quantization without smoothing causes perplexity degradation > 15 points due to outlier channels.",
        tags=["pitfall", "negative"],
    )

    # 6. Add Architectural Decision
    dec_mem = m_svc.add_memory(
        project_id="qat-study",
        type=MemoryType.DECISION,
        title="Adopt Per-Channel Smoothing for Production Inference",
        content="Based on observation and negative failure, standardizing on per-channel smoothing with alpha=0.5.",
        related_memory_ids=[obs_mem.id, neg_mem.id],
    )

    # 7. Record Agent Shift Handoff
    h_svc = HandoffService(vault)
    h_svc.create_handoff(
        project_id="qat-study",
        task="INT4 SmoothQuant Validation",
        completed_work=["Validated smoothing hypothesis", "Logged pitfall on static per-tensor quantization"],
        current_progress="Achieved 5.68 perplexity with INT4",
        decisions_made=["Adopt per-channel smoothing"],
        next_steps=["Benchmark Triton INT4 GEMM kernels"],
        agent_id="standalone-agent",
    )

    # 8. Build Context Pack
    cb = ContextBuilder(vault)
    context_pack = cb.build_context("qat-study", context_mode="quick", max_tokens=3000)

    assert "Quantization Aware Training" in context_pack
    assert "Adopt Per-Channel Smoothing" in context_pack
    assert "Static Per-Tensor Quantization Failure" in context_pack

    # 9. Validate that files are standard Markdown on disk
    assert (p_dir / "PROJECT.md").is_file()
    assert (p_dir / "STATE.md").is_file()
    assert (p_dir / "INDEX.md").is_file()
    assert (p_dir / "HANDOFF.md").is_file()
    assert (p_dir / "observations" / f"{obs_mem.id}.md").is_file()
    assert (p_dir / "negative" / f"{neg_mem.id}.md").is_file()
    assert (p_dir / "decisions" / f"{dec_mem.id}.md").is_file()
    assert (p_dir / "references" / f"{ref_mem.id}.md").is_file()

    # Rebuild index and validate project integrity
    idx_res = p_svc.rebuild_index("qat-study")
    assert idx_res["active_memories"] == 6  # 5 memories + 1 handoff memory
    val_res = p_svc.validate_project("qat-study")
    assert val_res["valid"] is True
    assert val_res["broken_links"] == []
