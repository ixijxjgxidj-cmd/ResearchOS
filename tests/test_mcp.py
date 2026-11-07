"""Test H: MCP server tools invocation and validation."""

from pathlib import Path
from researchos.adapters.mcp_server import (
    research_audit,
    research_context_build,
    research_experiment_create,
    research_experiment_validate,
    research_project_create,
    research_project_list,
    research_run_complete,
    research_run_create,
)


def test_mcp_tools(vault_dir: Path):
    v_str = str(vault_dir)

    # 1. Project create
    p_res = research_project_create(
        name="MCP Verification Project",
        research_question="Can MCP tools coordinate research workflows?",
        vault_root=v_str,
    )
    assert p_res["status"] == "success"
    proj_id = p_res["id"]
    assert proj_id.startswith("PRJ-")

    # 2. Project list
    p_list = research_project_list(vault_root=v_str)
    assert p_list["status"] == "success"
    assert any(p["id"] == proj_id for p in p_list["projects"])

    # 3. Experiment create
    e_res = research_experiment_create(
        project_id=proj_id,
        title="MCP Tooling Experiment",
        hypothesis="All MCP endpoints conform to schema contracts.",
        method="Call tool handlers in sequence.",
        planned_parameters={"batch": 16},
        success_criteria=["status == success"],
        vault_root=v_str,
    )
    assert e_res["status"] == "success"
    exp_id = e_res["id"]

    # 4. Experiment validate (preflight)
    val_res = research_experiment_validate(experiment_id=exp_id, vault_root=v_str)
    assert val_res["status"] == "success"
    assert val_res["preflight"] == "passed"

    # 5. Run create
    r_res = research_run_create(
        experiment_id=exp_id,
        agent_name="mcp_test_agent",
        vault_root=v_str,
    )
    assert r_res["status"] == "success"
    run_id = r_res["id"]

    # 6. Run complete
    comp_res = research_run_complete(
        run_id=run_id,
        actual_parameters={"batch": 16, "lr": 0.001},
        status="succeeded",
        experiment_outcome="positive",
        metrics={"accuracy": 0.99},
        result_summary="MCP test run verified.",
        vault_root=v_str,
    )
    assert comp_res["status"] == "success"

    # 7. Context build
    ctx_res = research_context_build(target_id=exp_id, vault_root=v_str)
    assert ctx_res["status"] == "success"
    assert "MCP Verification Project" in ctx_res["context_pack"]

    # 8. Audit
    aud_res = research_audit(project_id=proj_id, vault_root=v_str)
    assert "errors" in aud_res
