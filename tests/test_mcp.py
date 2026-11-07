"""Test: MCP Server tool execution and responses for v2 Universal Memory."""

from pathlib import Path

from researchos.interfaces.mcp.server import (
    context_build,
    handoff_create,
    handoff_get,
    index_rebuild,
    memory_add,
    memory_archive,
    memory_get,
    memory_search,
    memory_supersede,
    memory_update,
    project_create,
    project_get,
    project_list,
    project_validate,
)


def test_mcp_tools_lifecycle(tmp_path: Path):
    v_str = str(tmp_path / "vault")

    # 1. project_create
    p_res = project_create(
        name="MCP Protocol Project",
        project_id="mcp-proj",
        description="Testing MCP server tools",
        research_goal="Verify MCP compatibility",
        vault_root=v_str,
    )
    assert p_res["status"] == "success"
    assert p_res["project_id"] == "mcp-proj"

    # 2. project_list
    l_res = project_list(vault_root=v_str)
    assert l_res["status"] == "success"
    assert l_res["total"] == 1

    # 3. project_get
    g_res = project_get(project_id="mcp-proj", vault_root=v_str)
    assert g_res["status"] == "success"
    assert g_res["project_name"] == "MCP Protocol Project"

    # 4. memory_add
    m_res = memory_add(
        project_id="mcp-proj",
        type="observation",
        title="Inference Speedup with vLLM PagedAttention",
        content="PagedAttention delivers 3.5x higher serving throughput.",
        tags=["inference", "vllm"],
        source_agent="agent-mcp",
        source_skill="serving-skill",
        confidence=0.96,
        vault_root=v_str,
    )
    assert m_res["status"] == "success"
    mem_id = m_res["memory_id"]
    assert mem_id.startswith("MEM-")

    # 5. memory_get
    mg_res = memory_get(project_id="mcp-proj", memory_id=mem_id, vault_root=v_str)
    assert mg_res["status"] == "success"
    assert mg_res["title"] == "Inference Speedup with vLLM PagedAttention"
    assert mg_res["confidence"] == 0.96

    # 6. memory_search
    s_res = memory_search(project_id="mcp-proj", query="PagedAttention", vault_root=v_str)
    assert s_res["status"] == "success"
    assert s_res["total_hits"] >= 1
    assert s_res["hits"][0]["memory_id"] == mem_id

    # 7. memory_update
    u_res = memory_update(project_id="mcp-proj", memory_id=mem_id, confidence=0.99, vault_root=v_str)
    assert u_res["status"] == "success"

    # 8. memory_supersede
    sup_res = memory_supersede(
        project_id="mcp-proj",
        old_memory_id=mem_id,
        title="PagedAttention v2 Further Reduces KV Cache Fragmentation",
        content="PagedAttention v2 adds continuous batching and reduces waste by 12%.",
        reason="Upgraded vLLM backend to release 0.6.",
        vault_root=v_str,
    )
    assert sup_res["status"] == "success"
    new_mem_id = sup_res["new_memory_id"]

    # 9. memory_archive
    arc_res = memory_archive(project_id="mcp-proj", memory_id=new_mem_id, reason="Completed milestone", vault_root=v_str)
    assert arc_res["status"] == "success"
    assert arc_res["status_field"] == "archived"

    # 10. context_build
    ctx_res = context_build(project_id="mcp-proj", context_mode="quick", max_tokens=3000, vault_root=v_str)
    assert ctx_res["status"] == "success"
    assert "MCP Protocol Project" in ctx_res["context_pack"]

    # 11. handoff_create & handoff_get
    h_res = handoff_create(
        project_id="mcp-proj",
        task="MCP verification suite",
        completed_work=["Validated all tools"],
        current_progress="Ready for deployment",
        agent_id="test-runner",
        vault_root=v_str,
    )
    assert h_res["status"] == "success"

    hg_res = handoff_get(project_id="mcp-proj", vault_root=v_str)
    assert hg_res["status"] == "success"
    assert "MCP verification suite" in hg_res["handoff_content"]

    # 12. index_rebuild & project_validate
    idx_res = index_rebuild(project_id="mcp-proj", vault_root=v_str)
    assert idx_res["status"] == "success"

    val_res = project_validate(project_id="mcp-proj", vault_root=v_str)
    assert val_res["valid"] is True
