"""Comprehensive Acceptance Test Suite for ResearchOS Universal Memory (Tests 1 - 10)."""

import concurrent.futures
import shutil
from pathlib import Path

from researchos.core.context_builder import ContextBuilder, estimate_tokens
from researchos.core.handoff_service import HandoffService
from researchos.core.memory_service import MemoryService
from researchos.core.project_service import ProjectService
from researchos.core.retrieval_service import RetrievalService
from researchos.interfaces.mcp.server import (
    memory_add,
    memory_get,
    project_create,
)
from researchos.models.memory import MemoryStatus, MemoryType


# -------------------------------------------------------------------------
# Test 1: Project Independent Creation
# -------------------------------------------------------------------------
def test_1_project_independent_creation(tmp_path: Path):
    """Creates Project A and Project B; verifies independent folders, states, indexes, zero collisions."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)

    proj_a = ps.create_project(
        name="Project Alpha",
        project_id="proj-a",
        description="First independent study",
        research_goal="Explore transformer efficiency",
    )
    proj_b = ps.create_project(
        name="Project Beta",
        project_id="proj-b",
        description="Second independent study",
        research_goal="Investigate state space models",
    )

    dir_a = Path(proj_a.project_dir)
    dir_b = Path(proj_b.project_dir)

    assert dir_a.exists() and dir_a.is_dir()
    assert dir_b.exists() and dir_b.is_dir()
    assert dir_a != dir_b

    # Verify independent PROJECT.md, STATE.md, INDEX.md, HANDOFF.md
    for f in ("PROJECT.md", "STATE.md", "INDEX.md", "HANDOFF.md"):
        assert (dir_a / f).exists(), f"Missing {f} in Project A"
        assert (dir_b / f).exists(), f"Missing {f} in Project B"

    # Verify contents are independent
    assert "transformer efficiency" in (dir_a / "STATE.md").read_text(encoding="utf-8")
    assert "state space models" in (dir_b / "STATE.md").read_text(encoding="utf-8")

    # Idempotent re-creation check
    proj_a_re = ps.create_project(name="Project Alpha", project_id="proj-a")
    assert proj_a_re.project_id == "proj-a"


# -------------------------------------------------------------------------
# Test 2: Cross-Agent Memory Sharing
# -------------------------------------------------------------------------
def test_2_cross_agent_memory_sharing(tmp_path: Path):
    """Agent A writes memory in session 1; Agent B in separate session reads identical content and ID."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Shared Knowledge Project", project_id="shared-proj")

    # Session 1: Agent A writes memory
    ms_agent_a = MemoryService(vault)
    mem_created = ms_agent_a.add_memory(
        project_id="shared-proj",
        type=MemoryType.KNOWLEDGE,
        title="Attention Mechanism Scaling Law",
        content="Self-attention compute scales quadratically O(N^2) with sequence length N.",
        tags=["theory", "scaling"],
        source_agent="agent-alpha",
        source_skill="literature-analysis",
        confidence=0.99,
    )
    assigned_id = mem_created.id

    # Session 2: Agent B spawns in independent process/instance
    ms_agent_b = MemoryService(vault)
    mem_read = ms_agent_b.get_memory("shared-proj", assigned_id)

    assert mem_read.id == assigned_id
    assert mem_read.title == "Attention Mechanism Scaling Law"
    assert mem_read.type == MemoryType.KNOWLEDGE
    assert "quadratically O(N^2)" in mem_read.content
    assert mem_read.frontmatter.source_agent == "agent-alpha"
    assert mem_read.frontmatter.confidence == 0.99


# -------------------------------------------------------------------------
# Test 3: Project Isolation
# -------------------------------------------------------------------------
def test_3_project_isolation(tmp_path: Path):
    """Project A has unique memory; searching Project B by default never returns it."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Project Red", project_id="proj-red")
    ps.create_project("Project Blue", project_id="proj-blue")

    ms = MemoryService(vault)
    ms.add_memory(
        project_id="proj-red",
        type=MemoryType.OBSERVATION,
        title="SuperSecretObservationRed",
        content="Red-specific breakthrough metrics: +45% throughput.",
        tags=["red-secret"],
    )

    rs = RetrievalService(vault)
    # Search in Project Blue for 'SuperSecretObservationRed'
    hits_blue = rs.search_memories(
        project_id="proj-blue",
        query="SuperSecretObservationRed",
    )
    assert len(hits_blue) == 0, "Security isolation leak: Project B returned Project A's private memory!"

    # Search in Project Red should find it
    hits_red = rs.search_memories(
        project_id="proj-red",
        query="SuperSecretObservationRed",
    )
    assert len(hits_red) == 1
    assert hits_red[0].project_id == "proj-red"


# -------------------------------------------------------------------------
# Test 4: Context Recovery
# -------------------------------------------------------------------------
def test_4_context_recovery(tmp_path: Path):
    """Agent A writes knowledge, decisions, observations, handoff. Session terminates. Agent B restores full context."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Recovery Project", project_id="rec-proj")

    ms = MemoryService(vault)
    hs = HandoffService(vault)

    # Agent A writes decisions and negative lessons
    ms.add_memory(
        project_id="rec-proj",
        type=MemoryType.DECISION,
        title="Adopt PyTorch 2.4 Compile",
        content="Decided to use torch.compile(mode='reduce-overhead') for 20% speedup.",
        source_agent="agent-1",
    )
    ms.add_memory(
        project_id="rec-proj",
        type=MemoryType.NEGATIVE,
        title="BF16 Underflows in LayerNorm",
        content="Using bfloat16 for LayerNorm variance causes NaN loss after 500 steps. Always keep fp32 for norms.",
        source_agent="agent-1",
    )

    # Agent A concludes shift with Handoff
    hs.create_handoff(
        project_id="rec-proj",
        task="Baseline Training Run",
        completed_work=["Configured DDP", "Profiled memory"],
        current_progress="Completed epoch 1 with loss 2.45",
        unresolved_items=["Loss spike at iteration 1200"],
        next_steps=["Inspect learning rate warmup schedule"],
        agent_id="agent-1",
    )

    # Session terminates. New Agent B enters in fresh session
    cb = ContextBuilder(vault)
    context_pack = cb.build_context(
        project_id="rec-proj",
        task="Inspect learning rate warmup schedule",
        context_mode="task",
        max_tokens=4000,
    )

    assert "Recovery Project" in context_pack
    assert "Adopt PyTorch 2.4 Compile" in context_pack
    assert "BF16 Underflows in LayerNorm" in context_pack
    assert "Completed epoch 1 with loss 2.45" in context_pack
    assert "Inspect learning rate warmup schedule" in context_pack
    assert "**Source**:" in context_pack


# -------------------------------------------------------------------------
# Test 5: Concurrent Writing
# -------------------------------------------------------------------------
def test_5_concurrent_writing(tmp_path: Path):
    """Multiple concurrent threads writing memories to the same project; no file corruptions, lost writes, or ID collisions."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Concurrency Project", project_id="concurrent-proj")

    ms = MemoryService(vault)
    num_writes = 20

    def worker_write(index: int) -> str:
        mem = ms.add_memory(
            project_id="concurrent-proj",
            type=MemoryType.OBSERVATION,
            title=f"Concurrent Metric Batch #{index}",
            content=f"Empirical data log from concurrent thread #{index} with payload details.",
            tags=["concurrency", f"worker-{index % 4}"],
            source_agent=f"agent-{index % 4}",
        )
        return mem.id

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker_write, i) for i in range(num_writes)]
        created_ids = [f.result() for f in concurrent.futures.as_completed(futures)]

    # All IDs must be unique
    assert len(created_ids) == num_writes
    assert len(set(created_ids)) == num_writes

    # Validate project integrity
    val_res = ps.validate_project("concurrent-proj")
    assert val_res["valid"] is True
    assert val_res["total_memories"] == num_writes

    # Validate index count
    idx_res = ps.rebuild_index("concurrent-proj")
    assert idx_res["active_memories"] == num_writes


# -------------------------------------------------------------------------
# Test 6: Project Migration / Portability
# -------------------------------------------------------------------------
def test_6_project_migration(tmp_path: Path):
    """Copying the entire project directory to another machine/location preserves all memories, state, and relative links."""
    vault1 = tmp_path / "vault1"
    vault2 = tmp_path / "vault2"

    ps1 = ProjectService(vault1)
    ps1.create_project("Portable Project", project_id="portable-proj")

    ms1 = MemoryService(vault1)
    mem1 = ms1.add_memory(
        project_id="portable-proj",
        type=MemoryType.KNOWLEDGE,
        title="Quantization Formula",
        content="W_q = round(W / scale) + zero_point",
    )

    # Physically copy project folder to vault2
    src_proj_dir = vault1 / "portable-proj"
    dst_proj_dir = vault2 / "portable-proj"
    shutil.copytree(src_proj_dir, dst_proj_dir)

    # Connect new service to vault2
    ps2 = ProjectService(vault2)
    ms2 = MemoryService(vault2)

    proj_loaded = ps2.get_project("portable-proj")
    assert proj_loaded.project_name == "Portable Project"

    mem_loaded = ms2.get_memory("portable-proj", mem1.id)
    assert mem_loaded.title == "Quantization Formula"
    assert "W_q = round(W / scale)" in mem_loaded.content

    # Validate project in destination
    val = ps2.validate_project("portable-proj")
    assert val["valid"] is True
    assert val["broken_links"] == []


# -------------------------------------------------------------------------
# Test 7: Context Token Budget Enforcement
# -------------------------------------------------------------------------
def test_7_context_budget(tmp_path: Path):
    """Constructs project with extensive history; verifies budget enforcement, priority retention, negative knowledge preservation."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Budget Test Project", project_id="budget-proj")

    ms = MemoryService(vault)

    # Create critical negative lesson
    ms.add_memory(
        project_id="budget-proj",
        type=MemoryType.NEGATIVE,
        title="Critical Pitfall: Never Use SGD without Momentum on Vision Transformers",
        content="Pure SGD diverges completely on ViT-Base architectures. Always pair with AdamW or SGD-M with beta=0.9.",
    )

    # Create 30 verbose observations
    for i in range(30):
        ms.add_memory(
            project_id="budget-proj",
            type=MemoryType.OBSERVATION,
            title=f"Verbose Log Benchmark Evaluation Run #{i:02d}",
            content="Heavy verbose log benchmark results: " + ("metric_val: 0.98234, iter_step: 4000; " * 30),
        )

    cb = ContextBuilder(vault)

    # 1. Quick Context with budget
    budget_quick = 1200
    pack_quick = cb.build_context("budget-proj", context_mode="quick", max_tokens=budget_quick)
    tokens_quick = estimate_tokens(pack_quick)
    assert tokens_quick <= budget_quick + 50  # within margin
    assert "Critical Pitfall" in pack_quick
    assert "**Source**:" in pack_quick
    assert "omitted to respect" in pack_quick

    # 2. Task Context with budget
    budget_task = 1500
    pack_task = cb.build_context(
        "budget-proj",
        task="Vision Transformers SGD",
        context_mode="task",
        max_tokens=budget_task,
    )
    tokens_task = estimate_tokens(pack_task)
    assert tokens_task <= budget_task + 50
    assert "Critical Pitfall" in pack_task

    # 3. Full Context with budget
    budget_full = 1800
    pack_full = cb.build_context("budget-proj", context_mode="full", max_tokens=budget_full)
    tokens_full = estimate_tokens(pack_full)
    assert tokens_full <= budget_full + 50
    assert "Critical Pitfall" in pack_full


# -------------------------------------------------------------------------
# Test 8: Memory Superseding & Revision
# -------------------------------------------------------------------------
def test_8_memory_supersede_and_revision(tmp_path: Path):
    """Creates initial knowledge; revises with supersedes; old memory stays intact with status superseded; new memory links it."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Hypothesis Revision", project_id="rev-proj")

    ms = MemoryService(vault)
    old_mem = ms.add_memory(
        project_id="rev-proj",
        type=MemoryType.HYPOTHESIS,
        title="FP8 Training is Inherently Unstable",
        content="Initial experiments with E4M3 format failed to converge past step 200.",
    )

    # Overturn old finding with new evidence
    new_mem = ms.supersede_memory(
        project_id="rev-proj",
        old_memory_id=old_mem.id,
        title="Delayed Scaling Enables Stable FP8 Training",
        content="Using delayed scaling factors with 16-step lookahead stabilizes FP8 completely, matching FP16 convergence.",
        reason="Found that immediate scaling factor updates caused gradient oscillation. Delayed scaling solves this.",
        type=MemoryType.OBSERVATION,
    )

    # Verify old memory is preserved and marked superseded
    old_reloaded = ms.get_memory("rev-proj", old_mem.id)
    assert old_reloaded.status == MemoryStatus.SUPERSEDED
    assert "Initial experiments with E4M3" in old_reloaded.content

    # Verify new memory links to old memory
    assert new_mem.supersedes == old_mem.id
    assert new_mem.status == MemoryStatus.ACTIVE
    assert "Delayed Scaling Enables Stable FP8 Training" in new_mem.title

    # Search: active queries should be able to filter for active vs superseded
    rs = RetrievalService(vault)
    active_hits = rs.search_memories("rev-proj", status="active")
    assert any(h.memory_id == new_mem.id for h in active_hits)
    assert not any(h.memory_id == old_mem.id for h in active_hits)


# -------------------------------------------------------------------------
# Test 9: Server Restart & Persistence
# -------------------------------------------------------------------------
def test_9_server_restart_persistence(tmp_path: Path):
    """Simulates stopping and restarting the MCP server / process; all data remains 100% durable on filesystem."""
    vault = tmp_path / "vault"

    # Process 1 creates data via MCP tool functions
    res_p = project_create("Durable Project", project_id="dur-proj", vault_root=str(vault))
    assert res_p["status"] == "success"

    res_m = memory_add(
        project_id="dur-proj",
        type="decision",
        title="Architecture Decision: Shared Memory",
        content="Adopt Markdown-first flat structure.",
        vault_root=str(vault),
    )
    assert res_m["status"] == "success"
    mem_id = res_m["memory_id"]

    # Process 1 completely terminates. Simulated restart with brand new process call
    res_get = memory_get(project_id="dur-proj", memory_id=mem_id, vault_root=str(vault))
    assert res_get["status"] == "success"
    assert res_get["memory_id"] == mem_id
    assert res_get["title"] == "Architecture Decision: Shared Memory"


# -------------------------------------------------------------------------
# Test 10: Index Rebuild & Recovery
# -------------------------------------------------------------------------
def test_10_index_recovery(tmp_path: Path):
    """Deletes INDEX.md completely. Runs index_rebuild. Reconstructs all memories from disk without data loss."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Index Recovery Project", project_id="idx-proj")

    ms = MemoryService(vault)
    ms.add_memory("idx-proj", MemoryType.KNOWLEDGE, "Item 1", "Body 1")
    ms.add_memory("idx-proj", MemoryType.OBSERVATION, "Item 2", "Body 2")
    ms.add_memory("idx-proj", MemoryType.DECISION, "Item 3", "Body 3")

    p_dir = ps.get_project_dir("idx-proj")
    index_file = p_dir / "INDEX.md"
    assert index_file.exists()

    # Delete INDEX.md
    index_file.unlink()
    assert not index_file.exists()

    # Rebuild index
    rebuild_res = ps.rebuild_index("idx-proj")
    assert rebuild_res["status"] == "success"
    assert rebuild_res["active_memories"] == 3

    assert index_file.exists()
    content = index_file.read_text(encoding="utf-8")
    assert "Item 1" in content
    assert "Item 2" in content
    assert "Item 3" in content
