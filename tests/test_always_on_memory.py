"""Tests for Always-on Project Memory (MEMORY.md) and Paper Writing Mode (Section 16)."""

import concurrent.futures
from pathlib import Path

from researchos.core.context_builder import ContextBuilder, estimate_tokens
from researchos.core.memory_service import MemoryService
from researchos.core.paper_service import PaperService
from researchos.core.project_memory_service import ProjectMemoryService
from researchos.core.project_service import ProjectService
from researchos.models.memory import MemoryType


def test_1_each_project_independent_memory_md(tmp_path: Path):
    """1. Every project has an independent MEMORY.md."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Project Alpha", project_id="proj-alpha")

    pms = ProjectMemoryService(vault)
    mem_file = pms.get_memory_file("proj-alpha")
    assert mem_file.exists()

    content = pms.get_project_memory("proj-alpha")
    assert "Always-on Project Memory: Project Alpha" in content
    assert "Project Identity" in content
    assert "STABLE MEMORY" in content


def test_2_project_isolation_memory_md(tmp_path: Path):
    """2. Different projects' MEMORY.md do not leak into each other."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Project Alpha", project_id="proj-alpha")
    ps.create_project("Project Beta", project_id="proj-beta")

    pms = ProjectMemoryService(vault)
    pms.update_project_memory("proj-alpha", "## 1. Project Identity\nSecret Alpha Insight")
    pms.update_project_memory("proj-beta", "## 1. Project Identity\nSecret Beta Insight")

    alpha_text = pms.get_project_memory("proj-alpha")
    beta_text = pms.get_project_memory("proj-beta")

    assert "Secret Alpha Insight" in alpha_text
    assert "Secret Beta Insight" not in alpha_text

    assert "Secret Beta Insight" in beta_text
    assert "Secret Alpha Insight" not in beta_text


def test_3_quick_context_auto_includes_memory_md(tmp_path: Path):
    """3. New session Quick Context automatically includes MEMORY.md."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Quick Context Test", project_id="qc-proj")

    pms = ProjectMemoryService(vault)
    pms.update_project_memory(
        "qc-proj",
        "## 1. Project Identity\n- Research Topic: Quick Context Orientation\n## 2. Core Research Idea\n- Fast boot.",
    )

    cb = ContextBuilder(vault)
    pack = cb.build_context("qc-proj", context_mode="quick")

    assert "Always-on Project Memory" in pack
    assert "Quick Context Orientation" in pack
    assert "qc-proj/MEMORY.md" in pack


def test_4_context_compression_recovery_includes_memory_md(tmp_path: Path):
    """4. Quick context after context compression re-fetches MEMORY.md."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Compression Test", project_id="comp-proj")

    cb = ContextBuilder(vault)
    # Simulate first session boot
    pack1 = cb.build_context("comp-proj", context_mode="quick")
    assert "Always-on Project Memory" in pack1

    # Simulate shift update to MEMORY.md
    pms = ProjectMemoryService(vault)
    pms.update_project_memory("comp-proj", "## 1. Project Identity\nUpdated State After Compression")

    # Re-fetch Quick Context after hypothetical compression
    pack2 = cb.build_context("comp-proj", context_mode="quick")
    assert "Updated State After Compression" in pack2


def test_5_memory_md_does_not_load_all_detailed_memories(tmp_path: Path):
    """5. MEMORY.md does not automatically load all detailed memories."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Large Corpus Project", project_id="large-proj")
    ms = MemoryService(vault)

    # Add 20 extensive detailed memories
    for i in range(20):
        ms.add_memory(
            project_id="large-proj",
            type=MemoryType.OBSERVATION,
            title=f"Detailed Benchmark Result #{i:02d}",
            content="Heavy numerical metrics: " + ("12345.6789, " * 50),
        )

    pms = ProjectMemoryService(vault)
    mem_text = pms.get_project_memory("large-proj")

    # MEMORY.md should have executive pointers, but NOT all 20 heavy body texts
    assert "Heavy numerical metrics: 12345.6789" not in mem_text
    tokens = estimate_tokens(mem_text)
    assert tokens < 1500  # Stays lean within budget


def test_6_read_single_memory_by_id(tmp_path: Path):
    """6. Single memory can be read on demand by memory_id."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Single Read Project", project_id="single-proj")
    ms = MemoryService(vault)

    m = ms.add_memory(
        project_id="single-proj",
        type=MemoryType.OBSERVATION,
        title="Specific Empirical Finding",
        content="Precise experimental measurement: throughput=4200 rps.",
    )

    # Agent reads single memory directly
    fetched = ms.get_memory("single-proj", m.id)
    assert fetched.id == m.id
    assert "throughput=4200 rps" in fetched.content


def test_7_query_by_paper_section(tmp_path: Path):
    """7. Experiment catalog can be queried by paper_section."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Paper Study", project_id="paper-proj")
    ms = MemoryService(vault)
    paper_svc = PaperService(vault)

    ms.add_memory(
        project_id="paper-proj",
        type=MemoryType.OBSERVATION,
        title="ViT-Large Scale Ablation",
        content="Ablation on depth vs width.",
        paper_section="4.2 Ablation Study",
        metrics_summary="Acc: 84.2%",
    )
    ms.add_memory(
        project_id="paper-proj",
        type=MemoryType.OBSERVATION,
        title="Baseline Comparison against ResNet-152",
        content="Outperforms ResNet by 4.1%.",
        paper_section="4.1 Main Results",
        metrics_summary="Top-1: 88.5%",
    )

    items_ablation = paper_svc.get_paper_inventory("paper-proj", paper_section="4.2 Ablation Study")
    assert len(items_ablation) == 1
    assert items_ablation[0].title == "ViT-Large Scale Ablation"
    assert items_ablation[0].metrics_summary == "Acc: 84.2%"

    items_main = paper_svc.get_paper_inventory("paper-proj", paper_section="4.1 Main Results")
    assert len(items_main) == 1
    assert items_main[0].title == "Baseline Comparison against ResNet-152"


def test_8_paper_mode_identifies_failed_and_interrupted(tmp_path: Path):
    """8. Paper mode identifies Failed and Interrupted experiments without omission."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Robustness Study", project_id="rob-proj")
    ms = MemoryService(vault)
    paper_svc = PaperService(vault)

    # Completed
    ms.add_memory(
        project_id="rob-proj",
        type=MemoryType.OBSERVATION,
        title="Standard Normal Run",
        content="Success.",
        paper_section="4.1 Main Results",
    )
    # Failed run
    ms.add_memory(
        project_id="rob-proj",
        type=MemoryType.NEGATIVE,
        title="Adam without warmup diverges",
        content="Loss NaN at step 200.",
        paper_section="4.1 Main Results",
    )
    # Interrupted run
    ms.add_memory(
        project_id="rob-proj",
        type=MemoryType.OBSERVATION,
        title="Node Out-of-Memory Preemption",
        content="Killed by OOM.",
        tags=["interrupted"],
        paper_section="4.1 Main Results",
    )

    inventory = paper_svc.get_paper_inventory("rob-proj", paper_section="4.1 Main Results")
    statuses = {item.status for item in inventory}
    assert "completed" in statuses
    assert "failed" in statuses
    assert "interrupted" in statuses


def test_9_paper_mode_tracks_evidence_coverage(tmp_path: Path):
    """9. Paper mode maintains Evidence Coverage progress."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Evidence Project", project_id="ev-proj")
    ms = MemoryService(vault)
    paper_svc = PaperService(vault)

    m1 = ms.add_memory(
        project_id="ev-proj",
        type=MemoryType.OBSERVATION,
        title="Exp 1: Baseline",
        content="Result 1.",
        paper_section="4.1 Main Results",
    )
    m2 = ms.add_memory(
        project_id="ev-proj",
        type=MemoryType.OBSERVATION,
        title="Exp 2: Modified Head",
        content="Result 2.",
        paper_section="4.1 Main Results",
    )

    # Initial check: nothing loaded
    cov_init = paper_svc.check_evidence_coverage(
        project_id="ev-proj",
        paper_section="4.1 Main Results",
        loaded_memory_ids=[],
    )
    assert cov_init.is_fully_covered is False
    assert len(cov_init.pending_memory_ids) == 2

    # Load m1, exclude m2 with reason
    cov_partial = paper_svc.check_evidence_coverage(
        project_id="ev-proj",
        paper_section="4.1 Main Results",
        loaded_memory_ids=[m1.id],
        excluded_memory_ids={m2.id: "Ablation moved to Appendix"},
    )
    assert cov_partial.is_fully_covered is True
    assert len(cov_partial.pending_memory_ids) == 0


def test_10_memory_md_update_does_not_overwrite_detailed_memories(tmp_path: Path):
    """10. Updating MEMORY.md does not overwrite or mutate detailed memories."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Preservation Project", project_id="pres-proj")
    ms = MemoryService(vault)
    pms = ProjectMemoryService(vault)

    det = ms.add_memory(
        project_id="pres-proj",
        type=MemoryType.OBSERVATION,
        title="Detailed Record Title",
        content="Original uncompressed experimental proof.",
    )

    # Overwrite MEMORY.md with a new summary
    pms.update_project_memory("pres-proj", "## 1. Project Identity\nBrand new summary text.")

    # Detailed memory remains intact
    reloaded = ms.get_memory("pres-proj", det.id)
    assert reloaded.title == "Detailed Record Title"
    assert "Original uncompressed experimental proof." in reloaded.content


def test_11_conclusions_cite_memory_ids(tmp_path: Path):
    """11. Rebuilt MEMORY.md cites verified memory IDs for traceability."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Citation Project", project_id="cite-proj")
    ms = MemoryService(vault)
    pms = ProjectMemoryService(vault)

    m1 = ms.add_memory(
        project_id="cite-proj",
        type=MemoryType.OBSERVATION,
        title="Verified Convergence at Epoch 50",
        content="Metrics confirmed.",
    )
    m2 = ms.add_memory(
        project_id="cite-proj",
        type=MemoryType.NEGATIVE,
        title="Avoid RMSprop on Sparse Gradients",
        content="RMSprop oscillates violently.",
    )

    rebuilt = pms.rebuild_project_memory("cite-proj")
    assert m1.id in rebuilt
    assert m2.id in rebuilt

    val = pms.validate_project_memory("cite-proj")
    assert val["valid"] is True
    assert m1.id in val["cited_memory_ids"]
    assert m2.id in val["cited_memory_ids"]


def test_12_rebuild_project_memory_after_deletion(tmp_path: Path):
    """12. Deleting or corrupting MEMORY.md can be reconstructed seamlessly."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Reconstruction Project", project_id="rec-proj")
    pms = ProjectMemoryService(vault)

    mem_file = pms.get_memory_file("rec-proj")
    assert mem_file.exists()

    # Delete MEMORY.md
    mem_file.unlink()
    assert not mem_file.exists()

    # Rebuild from underlying project files and memories
    reconstructed = pms.rebuild_project_memory("rec-proj")
    assert mem_file.exists()
    assert "Always-on Project Memory: Reconstruction Project" in reconstructed


def test_13_concurrent_updates_to_memory_md(tmp_path: Path):
    """13. Concurrent updates to MEMORY.md do not corrupt the file."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Concurrency Project", project_id="conc-proj")
    pms = ProjectMemoryService(vault)

    def write_worker(agent_id: int):
        text = f"## 1. Project Identity\nWorker {agent_id} completed shift.\n## 2. Core Research Idea\nIdea {agent_id}."
        pms.update_project_memory("conc-proj", text, reason=f"Worker {agent_id}")
        return True

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(write_worker, i) for i in range(12)]
        results = [f.result() for f in futures]

    assert all(results)
    final_text = pms.get_project_memory("conc-proj")
    assert "## 1. Project Identity" in final_text
    val = pms.validate_project_memory("conc-proj")
    assert val["valid"] is True


def test_14_token_budget_management_retains_pointers(tmp_path: Path):
    """14. Exceeding token budget compresses/prioritizes while retaining essential pointers."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Budget Limit Project", project_id="bl-proj")
    ms = MemoryService(vault)
    pms = ProjectMemoryService(vault)

    # Create 35 memories
    for i in range(35):
        ms.add_memory(
            project_id="bl-proj",
            type=MemoryType.OBSERVATION,
            title=f"Voluminous Experiment #{i:02d}",
            content="Heavy log details: " + ("metric_data_point_xyz, " * 40),
        )

    # Rebuild with budget
    rebuilt = pms.rebuild_project_memory("bl-proj", max_tokens=2000)
    tokens = estimate_tokens(rebuilt)
    assert tokens <= 2200
    assert "MEMORY POINTERS" in rebuilt
    assert "MEM-" in rebuilt
