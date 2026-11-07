"""Script to generate a realistic example ResearchVault using v2 Universal Memory."""

import shutil
from pathlib import Path

from researchos.core.context_builder import ContextBuilder
from researchos.core.handoff_service import HandoffService
from researchos.core.memory_service import MemoryService
from researchos.core.project_service import ProjectService
from researchos.models.memory import MemoryType


def main() -> None:
    vault_dir = Path("examples/example-vault")
    if vault_dir.exists():
        shutil.rmtree(vault_dir)
    vault_dir.mkdir(parents=True, exist_ok=True)

    p_svc = ProjectService(vault_dir)
    m_svc = MemoryService(vault_dir)
    h_svc = HandoffService(vault_dir)
    c_bld = ContextBuilder(vault_dir)

    # 1. Create Project
    p_svc.create_project(
        name="Deep Residual Scaling Laws",
        project_id="deep-residual-scaling",
        description="Scaling behavior of transformer layer width vs depth under fixed parameter budget.",
        research_goal="Compute Chinchilla-optimal compute frontiers for width vs depth.",
        tags=["scaling-laws", "transformers", "efficiency"],
    )

    # 2. Add Literature Reference
    ref_mem = m_svc.add_memory(
        project_id="deep-residual-scaling",
        type=MemoryType.REFERENCE,
        title="Training Compute-Optimal Large Language Models (Chinchilla)",
        content="Hoffmann et al. (2022). Demonstrates tokens and parameters should be scaled in equal proportions.",
        tags=["literature", "chinchilla"],
        source_ref="arXiv:2203.15556",
    )

    # 3. Add Hypothesis
    hyp_mem = m_svc.add_memory(
        project_id="deep-residual-scaling",
        type=MemoryType.HYPOTHESIS,
        title="Deeper Architectures Yield Lower Perplexity at Fixed 7B Flops",
        content="Doubling depth while halving hidden dimension width will yield strictly lower cross-entropy loss.",
        tags=["hypothesis", "depth-width"],
        related_memory_ids=[ref_mem.id],
    )

    # 4. Add Negative Experience
    neg_mem = m_svc.add_memory(
        project_id="deep-residual-scaling",
        type=MemoryType.NEGATIVE,
        title="Extreme Depth (>96 layers) Suffers Residual Dilution",
        content="Models with depth > 96 fail to propagate early-layer gradients effectively without ReZero or LayerNorm tuning.",
        tags=["pitfall", "architecture", "negative"],
    )

    # 5. Add Observation
    obs_mem = m_svc.add_memory(
        project_id="deep-residual-scaling",
        type=MemoryType.OBSERVATION,
        title="Optimal Depth-to-Width Ratio on 7B Frontier is 1:3.2",
        content="Empirical frontier shows optimal tradeoff occurs at 48 layers with 4096 hidden width.",
        tags=["empirical", "frontier"],
        related_memory_ids=[hyp_mem.id, neg_mem.id],
        confidence=0.94,
    )

    # 6. Add Decision
    m_svc.add_memory(
        project_id="deep-residual-scaling",
        type=MemoryType.DECISION,
        title="Adopt 48-Layer 4096-Width Configuration for Final Pretraining",
        content="Selected 48-layer configuration based on empirical frontier and avoiding extreme depth instability.",
        tags=["decision", "architecture"],
        related_memory_ids=[obs_mem.id],
    )

    # 7. Record Agent Shift Handoff
    h_svc.create_handoff(
        project_id="deep-residual-scaling",
        task="Ablation Analysis and Final Architecture Selection",
        completed_work=[
            "Trained 12 grid models across depth-width tradeoffs",
            "Identified residual dilution breakdown beyond 96 layers",
            "Derived optimal 1:3.2 ratio",
        ],
        current_progress="Final architecture selected (48 layers, 4096 width)",
        important_findings=[
            "Residual dilution causes instability in extreme depth",
            "Optimal perplexity is 4.82 on Wikitext-103",
        ],
        next_steps=[
            "Launch full 100B token pretraining with FP8 precision",
            "Monitor gradient norm stability during cosine decay",
        ],
        agent_id="lead-researcher",
    )

    # 8. Rebuild index
    p_svc.rebuild_index("deep-residual-scaling")

    # 9. Verify Context Builder
    pack = c_bld.build_context("deep-residual-scaling", context_mode="quick", max_tokens=3000)
    print("Example Vault successfully created at:", vault_dir.resolve())
    print("Generated Context Pack length:", len(pack))


if __name__ == "__main__":
    main()
