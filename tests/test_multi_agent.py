"""Tests for Multi-Agent Concurrency, Isolation, and Source Attribution Safety."""

import concurrent.futures
from pathlib import Path
import pytest

from researchos.core.handoff_service import HandoffService
from researchos.core.memory_service import MemoryService
from researchos.core.project_memory_service import ProjectMemoryService
from researchos.core.project_service import ProjectService
from researchos.models.memory import MemoryType


@pytest.fixture
def multi_agent_setup(tmp_path: Path):
    vault_dir = tmp_path / "ResearchVault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    ps = ProjectService(vault_dir)
    ms = MemoryService(vault_dir)
    hs = HandoffService(vault_dir)
    pms = ProjectMemoryService(vault_dir)

    ps.create_project(
        name="Multi Agent Collaboration Project",
        project_id="collab-jepa",
        research_goal="Simultaneous research across multiple autonomous agents",
    )

    return {
        "vault_dir": vault_dir,
        "ps": ps,
        "ms": ms,
        "hs": hs,
        "pms": pms,
        "project_id": "collab-jepa",
    }


def test_concurrent_memory_add_preserves_unique_ids_and_attribution(multi_agent_setup):
    ms: MemoryService = multi_agent_setup["ms"]
    pid = multi_agent_setup["project_id"]

    num_threads = 8
    items_per_thread = 3
    total_expected = num_threads * items_per_thread

    def worker(agent_idx: int):
        results = []
        agent_name = f"Agent-Worker-{agent_idx}"
        for i in range(items_per_thread):
            mem = ms.add_memory(
                project_id=pid,
                type=MemoryType.OBSERVATION,
                title=f"Worker {agent_idx} Finding {i}",
                content=f"Quantitative observation from worker {agent_idx} step {i}",
                source_agent=agent_name,
                tags=[f"worker-{agent_idx}", "concurrent"],
            )
            results.append(mem)
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, idx) for idx in range(num_threads)]
        all_created = []
        for f in concurrent.futures.as_completed(futures):
            all_created.extend(f.result())

    assert len(all_created) == total_expected

    # All generated IDs must be strictly unique
    ids = [m.id for m in all_created]
    assert len(ids) == len(set(ids)), "IDs must be strictly unique across concurrent additions"

    # All source agents must be preserved correctly
    for m in all_created:
        assert m.frontmatter.source_agent.startswith("Agent-Worker-")

    # Verify project index has all memories
    from researchos.core.retrieval_service import RetrievalService
    rs = RetrievalService(multi_agent_setup["vault_dir"])
    all_indexed = rs.search_memories(pid, limit=100)
    assert len(all_indexed) == total_expected


def test_concurrent_handoff_creation_safety(multi_agent_setup):
    hs: HandoffService = multi_agent_setup["hs"]
    pid = multi_agent_setup["project_id"]

    num_agents = 5

    def create_agent_handoff(idx: int):
        agent_name = f"Agent-Lead-{idx}"
        return hs.create_handoff(
            project_id=pid,
            task=f"Subtask Lead {idx} Complete",
            completed_work=[f"Lead {idx} verified checkpoints"],
            next_steps=[f"Lead {idx} recommended ablation"],
            agent_id=agent_name,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_agents) as executor:
        futures = [executor.submit(create_agent_handoff, idx) for idx in range(num_agents)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == num_agents

    # Verify HANDOFF.md exists and is readable
    vault_dir = multi_agent_setup["vault_dir"]
    handoff_path = vault_dir / pid / "HANDOFF.md"
    assert handoff_path.exists()
    content = handoff_path.read_text(encoding="utf-8")
    assert "Agent-Lead-" in content


def test_concurrent_memory_rebuild_safety(multi_agent_setup):
    pms: ProjectMemoryService = multi_agent_setup["pms"]
    pid = multi_agent_setup["project_id"]

    num_callers = 6

    def rebuild_worker(idx: int):
        return pms.rebuild_project_memory(pid, preserve_custom_notes=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_callers) as executor:
        futures = [executor.submit(rebuild_worker, idx) for idx in range(num_callers)]
        outputs = [f.result() for f in concurrent.futures.as_completed(futures)]

    # All calls should return valid MEMORY.md markdown
    for out in outputs:
        assert "# MEMORY" in out
        assert "STABLE MEMORY" in out
        assert "WORKING MEMORY" in out
