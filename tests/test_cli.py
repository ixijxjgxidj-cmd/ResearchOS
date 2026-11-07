"""Test H: CLI commands invocation and output formats."""

import json
from pathlib import Path
from typer.testing import CliRunner
from researchos.adapters.cli import app

runner = CliRunner()


def test_cli_workflows(vault_dir: Path):
    v_str = str(vault_dir)

    # 1. Project create with --json
    res_p = runner.invoke(app, ["project", "create", "CLI Verification Project", "--vault", v_str, "--json"])
    assert res_p.exit_code == 0
    p_data = json.loads(res_p.stdout)
    proj_id = p_data["id"]
    assert proj_id.startswith("PRJ-")

    # 2. Project list
    res_list = runner.invoke(app, ["project", "list", "--vault", v_str])
    assert res_list.exit_code == 0
    assert "CLI Verification Project" in res_list.stdout

    # 3. Experiment create
    res_exp = runner.invoke(
        app,
        [
            "experiment", "create", proj_id, "CLI Experiment",
            "--exploratory",
            "--params", '{"lr": 0.01}',
            "--vault", v_str,
            "--json",
        ],
    )
    assert res_exp.exit_code == 0
    e_data = json.loads(res_exp.stdout)
    exp_id = e_data["id"]

    # 4. Run create
    res_run = runner.invoke(app, ["run", "create", exp_id, "--agent", "cli-tester", "--vault", v_str, "--json"])
    assert res_run.exit_code == 0
    r_data = json.loads(res_run.stdout)
    run_id = r_data["id"]

    # 5. Run complete
    res_comp = runner.invoke(
        app,
        [
            "run", "complete", run_id,
            "-p", '{"lr": 0.01, "epochs": 5}',
            "-s", "succeeded",
            "-o", "positive",
            "--vault", v_str,
            "--json",
        ],
    )
    assert res_comp.exit_code == 0

    # 6. Context build
    res_ctx = runner.invoke(app, ["context", "build", exp_id, "--vault", v_str])
    assert res_ctx.exit_code == 0
    assert "Research Context Pack" in res_ctx.stdout
    assert "CLI Verification Project" in res_ctx.stdout

    # 7. Audit
    res_audit = runner.invoke(app, ["audit", "--vault", v_str, "--json"])
    assert res_audit.exit_code == 0
    audit_data = json.loads(res_audit.stdout)
    assert "status" in audit_data
