"""Comprehensive unit and integration tests for BM25 search, Chinese/English tokenization, and relation graph traversal."""

from pathlib import Path

from researchos.core.memory_service import MemoryService
from researchos.core.project_service import ProjectService
from researchos.core.retrieval_service import RetrievalService, tokenize_text
from researchos.models.memory import MemoryType


def test_chinese_and_english_tokenization():
    text = "LLaMA-3.1 模型的量化分析 (QAT与GPTQ评估)"
    tokens = tokenize_text(text)
    # Checks Latin model names preserved
    assert "llama-3.1" in tokens or "llama" in tokens
    # Checks CJK unigrams and bigrams
    assert "量" in tokens
    assert "化" in tokens
    assert "量化" in tokens
    assert "分析" in tokens
    assert "评估" in tokens


def test_bm25_field_weighting_ranking(tmp_path: Path):
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Search Benchmark", project_id="search-proj")
    ms = MemoryService(vault)
    rs = RetrievalService(vault)

    # Mem 1: Matches in body only
    m1 = ms.add_memory(
        project_id="search-proj",
        type=MemoryType.OBSERVATION,
        title="Training Convergence on Cluster A",
        content="We observed gradient spikes during FlashAttention-2 compilation.",
    )

    # Mem 2: Matches in title
    m2 = ms.add_memory(
        project_id="search-proj",
        type=MemoryType.DECISION,
        title="Adoption of FlashAttention-2 in Core Pipeline",
        content="Decided to switch kernel implementations for 2x speedup.",
    )

    # Mem 3: Exact ID match test target
    m3 = ms.add_memory(
        project_id="search-proj",
        type=MemoryType.KNOWLEDGE,
        title="Attention Mechanisms Summary",
        content="Standard quadratic attention baseline notes.",
    )

    # Search by keyword "FlashAttention-2": Title match (m2) should rank higher than body match (m1)
    hits = rs.search_memories(project_id="search-proj", query="FlashAttention-2")
    assert len(hits) >= 2
    assert hits[0].memory_id == m2.id
    assert hits[1].memory_id == m1.id
    assert hits[0].score > hits[1].score

    # Exact ID search: should boost exact match to top
    id_hits = rs.search_memories(project_id="search-proj", query=m3.id)
    assert len(id_hits) >= 1
    assert id_hits[0].memory_id == m3.id
    assert id_hits[0].score >= 15.0


def test_chinese_research_query(tmp_path: Path):
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Chinese NLP Study", project_id="cjk-proj")
    ms = MemoryService(vault)
    rs = RetrievalService(vault)

    m1 = ms.add_memory(
        project_id="cjk-proj",
        type=MemoryType.KNOWLEDGE,
        title="大语言模型量化感知训练核心要点",
        content="在FP8量化过程中必须对激活值异常点进行平滑处理（SmoothQuant技术）。",
        tags=["量化", "大模型"],
    )

    # Unspaced Chinese query
    hits = rs.search_memories(project_id="cjk-proj", query="量化感知训练")
    assert len(hits) >= 1
    assert hits[0].memory_id == m1.id

    # Single Chinese character keyword
    char_hits = rs.search_memories(project_id="cjk-proj", query="模型")
    assert len(char_hits) >= 1
    assert char_hits[0].memory_id == m1.id


def test_multi_field_filters(tmp_path: Path):
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Filter Project", project_id="filter-proj")
    ms = MemoryService(vault)
    rs = RetrievalService(vault)

    m1 = ms.add_memory(
        project_id="filter-proj",
        type=MemoryType.OBSERVATION,
        title="High Precision Observation",
        content="Observed convergence under learning rate 3e-4.",
        tags=["lr", "optimizer"],
        source_agent="agent-alpha",
        source_skill="exp-runner",
        source_type="experiment",
        confidence=0.98,
    )
    ms.add_memory(
        project_id="filter-proj",
        type=MemoryType.HYPOTHESIS,
        title="Low Confidence Hypothesis",
        content="Perhaps weight decay 0.1 is too high.",
        tags=["lr"],
        source_agent="agent-beta",
        source_skill="planner",
        source_type="agent",
        confidence=0.45,
    )

    # Filter by source_agent
    hits_agent = rs.search_memories(project_id="filter-proj", source_agent="agent-alpha")
    assert len(hits_agent) == 1
    assert hits_agent[0].memory_id == m1.id

    # Filter by min_confidence
    hits_conf = rs.search_memories(project_id="filter-proj", min_confidence=0.90)
    assert len(hits_conf) == 1
    assert hits_conf[0].memory_id == m1.id

    # Filter by tags AND mode
    hits_and = rs.search_memories(project_id="filter-proj", tags=["lr", "optimizer"], tag_mode="AND")
    assert len(hits_and) == 1
    assert hits_and[0].memory_id == m1.id

    # Filter by tags OR mode
    hits_or = rs.search_memories(project_id="filter-proj", tags=["lr", "optimizer"], tag_mode="OR")
    assert len(hits_or) == 2


def test_relation_graph_traversal_and_cycle_prevention(tmp_path: Path):
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Relation Graph Project", project_id="graph-proj")
    ms = MemoryService(vault)
    rs = RetrievalService(vault)

    # Create root node A
    mA = ms.add_memory(
        project_id="graph-proj",
        type=MemoryType.KNOWLEDGE,
        title="Node A: Root Theory",
        content="Foundation concepts.",
    )

    # Create child B referencing A
    mB = ms.add_memory(
        project_id="graph-proj",
        type=MemoryType.OBSERVATION,
        title="Node B: Empirical Validation",
        content="Validating theory A.",
        related_memory_ids=[mA.id],
    )

    # Create child C referencing B
    mC = ms.add_memory(
        project_id="graph-proj",
        type=MemoryType.DECISION,
        title="Node C: Architecture Shift",
        content="Shift based on observation B.",
        related_memory_ids=[mB.id],
    )

    # Test depth 1 from B
    rel_depth1 = rs.search_related_graph("graph-proj", mB.id, max_depth=1)
    retrieved_ids = {r.memory_id for r in rel_depth1}
    assert mA.id in retrieved_ids
    assert mC.id in retrieved_ids

    # Test depth 2 from A: reaches B (depth 1) and C (depth 2)
    rel_depth2 = rs.search_related_graph("graph-proj", mA.id, max_depth=2)
    retrieved_from_A = {r.memory_id for r in rel_depth2}
    assert mB.id in retrieved_from_A
    assert mC.id in retrieved_from_A

    # Test cycle: update mA to point back to mC (forming A -> B -> C -> A)
    ms.update_memory("graph-proj", mA.id, related_memory_ids=[mC.id])
    # Traversal must finish without infinite recursion
    rel_cycle = rs.search_related_graph("graph-proj", mA.id, max_depth=3)
    assert len(rel_cycle) <= 2
