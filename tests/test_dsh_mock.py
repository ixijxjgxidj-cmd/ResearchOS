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
