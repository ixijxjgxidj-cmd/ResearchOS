"""Test J: DSH Infrastructure Integration Mock Testing."""

from pathlib import Path
import pytest
from researchos.core.enums import RunStatus
from researchos.integration.dsh.mock_adapter import MockDSHAdapter
from researchos.services.experiment_service import ExperimentService
from researchos.services.project_service import ProjectService
from researchos.services.run_service import RunService


def test_dsh_agent_workflow_mock(
    vault_dir: Path,
    project_service: ProjectService,
    experiment_service: ExperimentService,
    run_service: RunService,
):
    dsh = MockDSHAdapter()

    # 1. Agent discovers available A100 GPU servers
    servers = dsh.get_servers(gpu_model="A100", min_gpu_memory_gb=40)
    assert len(servers) >= 1
    target_server = servers[0]
    server_id = target_server["server_id"]
    assert server_id == "srv_a100_01"

    # 2. Agent creates experiment in ResearchOS
    proj = project_service.create_project(name="Remote GPU Training")
    exp = experiment_service.create_experiment(
        project_id=proj.id,
        title="Distributed Llama-3 Fine-tuning",
        is_exploratory=True,
    )

    # 3. Agent claims server with 120-minute lease
    claim_res = dsh.claim_server(
        server_id=server_id,
        agent="antigravity",
        task=f"run_training_{exp.id}",
        duration_minutes=120,
    )
    assert claim_res["status"] == "claimed"
    lease_id = claim_res["lease_id"]

    # 4. Agent attempts conflicting claim by another agent -> must fail
    with pytest.raises(RuntimeError) as exc_info:
        dsh.claim_server(server_id=server_id, agent="another_agent", task="steal_gpu")
    assert "already occupied" in str(exc_info.value)

    # 5. Agent initializes Run in ResearchOS with DSH server references
    isolated_workspace = f"~/workspace/train_{exp.id}_antigravity_20261107"
    run = run_service.create_run(
        experiment_id=exp.id,
        agent_name="antigravity",
        executor_type="dsh",
        server_id=server_id,
        server_task_id=lease_id,
        infrastructure_provider="dsh",
        working_directory=isolated_workspace,
        environment={"cuda": "12.4", "python": "3.11"},
    )
    assert run.server_id == server_id
    assert run.infrastructure_provider == "dsh"
    assert run.working_directory == isolated_workspace

    # 6. Agent performs backup via DSH
    backup_plan = dsh.plan_server_backup(
        server_id=server_id,
        session_name="llama3_ft",
        summary="epoch3_final",
        has_google_drive=True,
    )
    assert backup_plan["status"] == "planned"
    assert backup_plan["route"] == "gdrive"
    backup_ref = backup_plan["backup_reference"]

    # 7. Complete Run with backup reference
    run_service.complete_run(
        run_id=run.id,
        status=RunStatus.SUCCEEDED,
        actual_parameters={"lr": 5e-5, "lora_rank": 16},
        result_summary="Remote training succeeded on A100.",
    )
    run_service.update_run(run.id, {"backup_reference": backup_ref})

    # 8. Agent releases DSH server
    rel_res = dsh.release_server(server_id=server_id, agent="antigravity", task_done=True)
    assert rel_res["status"] == "released"

    # Server is idle again
    srv_after = dsh.get_servers(gpu_model="A100")[0]
    assert srv_after["current_task"] is None

    # 9. Security assertion: Verify NO sensitive keys/passwords in the markdown file
    run_file = vault_dir / "00-Projects" / proj.id / "Runs" / f"{run.id}.md"
    content = run_file.read_text(encoding="utf-8")
    for forbidden in ["password", "PRIVATE KEY", "api_key", "token"]:
        assert forbidden not in content or "[REDACTED_CREDENTIAL]" in content


def test_dsh_server_selection_and_local_fallback(
    vault_dir: Path,
    project_service: ProjectService,
    experiment_service: ExperimentService,
    run_service: RunService,
):
    """Verifies: 1) CPU server discovery/claiming; 2) Graceful fallback to local execution when no server is available."""
    dsh = MockDSHAdapter()
    proj = project_service.create_project(name="Heterogeneous Compute Project")
    exp = experiment_service.create_experiment(
        project_id=proj.id,
        title="CPU Benchmark & Fallback Test",
        is_exploratory=True,
    )

    # 1. Test finding a specific CPU server (e.g. LinuxONE)
    cpu_servers = dsh.get_servers(server_name_or_keyword="LinuxONE")
    assert len(cpu_servers) == 1
    assert cpu_servers[0]["name"] == "IBM-LinuxONE-s390x"

    # 2. Test requesting an unavailable/overspecified GPU (e.g. H100 160GB)
    rare_servers = dsh.get_servers(gpu_model="H100", min_gpu_memory_gb=160)
    assert len(rare_servers) == 0  # No server in pool matches

    # 3. Graceful Fallback Protocol: When DSH MCP has no available servers, fallback to local execution
    fallback_workspace = "./runs/RUN-LOCAL-FALLBACK"
    fallback_deviation = "Fallback to local execution: no available server in DSH MCP matching H100 (160GB)."

    run = run_service.create_run(
        experiment_id=exp.id,
        agent_name="antigravity",
        executor_type="local",
        server_id=None,
        server_task_id=None,
        infrastructure_provider="local_host",
        working_directory=fallback_workspace,
        actual_parameters={"cpu_threads": 4, "device": "cpu"},
    )
    assert run.executor_type == "local"
    assert run.server_id is None

    # Complete the run with fallback recorded in deviations
    completed_run = run_service.complete_run(
        run_id=run.id,
        status=RunStatus.SUCCEEDED,
        actual_parameters={"cpu_threads": 4, "device": "cpu"},
        deviations=[fallback_deviation],
        result_summary="Completed on local host via graceful fallback protocol.",
    )
    assert completed_run.status == RunStatus.SUCCEEDED
    assert fallback_deviation in completed_run.deviations

    # Verify run record in vault markdown reflects local execution and fallback deviation
    run_path = vault_dir / "00-Projects" / proj.id / "Runs" / f"{run.id}.md"
    markdown_content = run_path.read_text(encoding="utf-8")
    assert "executor_type: local" in markdown_content
    assert "Fallback to local execution" in markdown_content
