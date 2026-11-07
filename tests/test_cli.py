"""Test: CLI commands invocation and output formats for v2 Universal Memory."""

import json
from pathlib import Path

from typer.testing import CliRunner

from researchos.interfaces.cli.main import app

runner = CliRunner()


def test_cli_workflows(tmp_path: Path):
    v_str = str(tmp_path / "vault")

    # 1. Project create with --json
    res_p = runner.invoke(app, ["project", "create", "CLI Verification Project", "--id", "cli-proj", "--vault", v_str, "--json"])
    assert res_p.exit_code == 0
    p_data = json.loads(res_p.stdout)
    assert p_data["frontmatter"]["project_id"] == "cli-proj"

    # 2. Project list
    res_list = runner.invoke(app, ["project", "list", "--vault", v_str])
    assert res_list.exit_code == 0
    assert "CLI Verification Project" in res_list.stdout

    # 3. Memory add
    res_mem = runner.invoke(
        app,
        [
            "memory", "add", "cli-proj",
            "--type", "knowledge",
            "--title", "CLI Transformer Insight",
            "--content", "Transformers scale with parameter count and dataset size.",
            "--tag", "nlp",
            "--agent", "cli-agent",
            "--vault", v_str,
            "--json",
        ],
    )
    assert res_mem.exit_code == 0
    m_data = json.loads(res_mem.stdout)
    mem_id = m_data["frontmatter"]["id"]
    assert mem_id.startswith("MEM-")

    # 4. Memory get
    res_get = runner.invoke(app, ["memory", "get", "cli-proj", mem_id, "--vault", v_str, "--json"])
    assert res_get.exit_code == 0
    m_get_data = json.loads(res_get.stdout)
    assert m_get_data["frontmatter"]["title"] == "CLI Transformer Insight"

    # 5. Memory search
    res_search = runner.invoke(app, ["memory", "search", "cli-proj", "--query", "Transformer", "--vault", v_str, "--json"])
    assert res_search.exit_code == 0
    hits = json.loads(res_search.stdout)
    assert len(hits) >= 1
    assert hits[0]["memory_id"] == mem_id

    # 6. Context build
    res_ctx = runner.invoke(app, ["context", "build", "cli-proj", "--mode", "quick", "--vault", v_str])
    assert res_ctx.exit_code == 0
    assert "ResearchOS Context Pack" in res_ctx.stdout
    assert "CLI Verification Project" in res_ctx.stdout

    # 7. Handoff create & get
    res_handoff = runner.invoke(
        app,
        [
            "handoff", "create", "cli-proj",
            "--task", "CLI Verification Shift",
            "--completed", "Verified all CLI commands",
            "--progress", "All commands passed cleanly",
            "--vault", v_str,
            "--json",
        ],
    )
    assert res_handoff.exit_code == 0

    res_h_get = runner.invoke(app, ["handoff", "get", "cli-proj", "--vault", v_str])
    assert res_h_get.exit_code == 0
    assert "CLI Verification Shift" in res_h_get.stdout
