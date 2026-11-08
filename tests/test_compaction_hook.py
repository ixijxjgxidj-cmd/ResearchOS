"""Tests for Context Compaction Hook Core, Project Resolver, and Adapters."""

import os
import pytest
from pathlib import Path

from researchos.core.project_service import ProjectService
from researchos.core.memory_service import MemoryService
from researchos.core.handoff_service import HandoffService
from researchos.hooks.resolver import ProjectResolver, ProjectResolutionError
from researchos.hooks.core import MemoryHookCore, HookResult
from researchos.hooks.adapters.claude_code import ClaudeCodeAdapter
from researchos.hooks.adapters.antigravity import GeminiAntigravityAdapter
from researchos.hooks.adapters.codex import CodexAdapter
from researchos.hooks.adapters.generic_cli import GenericCLIAdapter


@pytest.fixture
def test_setup(tmp_path: Path):
    vault_dir = tmp_path / "ResearchVault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    ps = ProjectService(vault_dir)
    ms = MemoryService(vault_dir)
    hs = HandoffService(vault_dir)

    p1 = ps.create_project(
        name="Alpha Research",
        project_id="alpha-project",
        research_goal="Investigate self-supervised seismic signals",
    )
    p2 = ps.create_project(
        name="Beta Research",
        project_id="beta-project",
        research_goal="Evaluate graph neural network representations",
    )
    return {
        "vault_dir": vault_dir,
        "ps": ps,
        "ms": ms,
        "hs": hs,
        "p1": p1,
        "p2": p2,
    }


class TestProjectResolver:
    def test_resolve_explicit_id(self, test_setup):
        vault_dir = test_setup["vault_dir"]
        resolver = ProjectResolver(vault_dir)
        pid, pdir = resolver.resolve(project_id="alpha-project")
        assert pid == "alpha-project"
        assert pdir == vault_dir / "alpha-project"

    def test_resolve_explicit_id_not_found(self, test_setup):
        vault_dir = test_setup["vault_dir"]
        resolver = ProjectResolver(vault_dir)
        with pytest.raises(ProjectResolutionError, match="not found in vault"):
            resolver.resolve(project_id="gamma-nonexistent")

    def test_resolve_from_env_var(self, test_setup, monkeypatch):
        vault_dir = test_setup["vault_dir"]
        monkeypatch.setenv("RESEARCHOS_PROJECT_ID", "beta-project")
        resolver = ProjectResolver(vault_dir)
        pid, pdir = resolver.resolve()
        assert pid == "beta-project"
        assert pdir == vault_dir / "beta-project"

    def test_resolve_upward_from_subdir(self, test_setup):
        vault_dir = test_setup["vault_dir"]
        subdir = vault_dir / "alpha-project" / "records"
        subdir.mkdir(parents=True, exist_ok=True)

        resolver = ProjectResolver(vault_dir)
        pid, pdir = resolver.resolve(cwd=subdir)
        assert pid == "alpha-project"
        assert pdir == vault_dir / "alpha-project"

    def test_resolve_zero_guessing_fails_on_unresolvable_path(self, test_setup, monkeypatch):
        vault_dir = test_setup["vault_dir"]
        monkeypatch.delenv("RESEARCHOS_PROJECT_ID", raising=False)
        monkeypatch.delenv("PROJECT_ID", raising=False)
        unrelated_dir = test_setup["vault_dir"].parent / "unrelated_dir"
        unrelated_dir.mkdir(parents=True, exist_ok=True)

        resolver = ProjectResolver(vault_dir)
        with pytest.raises(ProjectResolutionError, match=r"resolve ResearchOS project"):
            resolver.resolve(cwd=unrelated_dir)


class TestMemoryHookCore:
    def test_session_start_injects_memory(self, test_setup):
        vault_dir = test_setup["vault_dir"]
        core = MemoryHookCore(vault_dir)
        res = core.on_session_start(project_id="alpha-project")
        assert res.success is True
        assert res.project_id == "alpha-project"
        assert res.context_text is not None
        assert "# MEMORY" in res.context_text
        assert "STABLE MEMORY" in res.context_text

    def test_pre_compaction_saves_state_and_handoff(self, test_setup):
        vault_dir = test_setup["vault_dir"]
        core = MemoryHookCore(vault_dir)

        res = core.on_pre_compaction(
            project_id="alpha-project",
            agent_id="Claude-3.7-Sonnet",
            task="Training 50 epochs with mask ratio 0.4",
            completed_work=["Completed baseline evaluation", "Fixed data loader leak"],
            next_steps=["Run ablation on patch size", "Plot latent loss curve"],
            blockers=["Pending GPU A100 availability"],
        )

        assert res.success is True
        assert res.project_id == "alpha-project"

        # Check that MEMORY.md was refreshed with current task and blockers
        p_mem_path = vault_dir / "alpha-project" / "MEMORY.md"
        assert p_mem_path.exists()
        content = p_mem_path.read_text(encoding="utf-8")
        assert "Training 50 epochs with mask ratio 0.4" in content
        assert "Pending GPU A100 availability" in content

    def test_post_compaction_restores_context(self, test_setup):
        vault_dir = test_setup["vault_dir"]
        core = MemoryHookCore(vault_dir)

        # Trigger pre-compaction first to set state
        core.on_pre_compaction(
            project_id="alpha-project",
            agent_id="Agent-A",
            task="Testing Stage Evaluation",
            next_steps=["Verify test loss"],
        )

        # Post-compaction hook restores memory for the compressed session
        res = core.on_post_compaction(project_id="alpha-project")
        assert res.success is True
        assert res.context_text is not None
        assert "# MEMORY" in res.context_text
        assert "Testing Stage Evaluation" in res.context_text
        assert "Verify test loss" in res.context_text

    def test_session_end_creates_handoff(self, test_setup):
        vault_dir = test_setup["vault_dir"]
        core = MemoryHookCore(vault_dir)

        res = core.on_session_end(
            project_id="alpha-project",
            agent_id="Agent-Finisher",
            task="Completed initial validation suite.",
            completed_work=["Run unit tests", "Export checkpoints"],
            next_steps=["Deploy inference pipeline"],
        )
        assert res.success is True

        handoff_path = vault_dir / "alpha-project" / "HANDOFF.md"
        assert handoff_path.exists()
        handoff_text = handoff_path.read_text(encoding="utf-8")
        assert "Completed initial validation suite." in handoff_text

    def test_idempotency_prevents_duplicate_writes(self, test_setup):
        vault_dir = test_setup["vault_dir"]
        core = MemoryHookCore(vault_dir)

        # First pre-compaction with explicit event_id
        res1 = core.on_pre_compaction(
            project_id="alpha-project",
            agent_id="Agent-A",
            task="Task A",
            event_id="evt-100",
        )
        assert res1.success is True
        assert res1.idempotent_skip is False

        # Rapid second call with same event_id
        res2 = core.on_pre_compaction(
            project_id="alpha-project",
            agent_id="Agent-A",
            task="Task A",
            event_id="evt-100",
        )
        assert res2.success is True
        assert res2.idempotent_skip is True

    def test_project_isolation(self, test_setup):
        vault_dir = test_setup["vault_dir"]
        core = MemoryHookCore(vault_dir)

        core.on_pre_compaction(
            project_id="alpha-project",
            agent_id="Agent-Alpha",
            task="Alpha Exclusive Stage Task",
        )

        res_beta = core.on_session_start(project_id="beta-project")
        assert "Alpha Exclusive Stage Task" not in res_beta.context_text
        assert "Beta Research" in res_beta.context_text


class TestHookAdapters:
    def test_claude_code_adapter(self, test_setup):
        vault_dir = test_setup["vault_dir"]
        adapter = ClaudeCodeAdapter(vault_dir)

        res_start = adapter.handle_session_start(project_id="alpha-project")
        assert res_start["status"] == "success"
        assert "additionalContext" in res_start
        assert "MEMORY" in res_start["additionalContext"]

        res_post = adapter.handle_post_compaction(project_id="alpha-project")
        assert res_post["status"] == "success"
        assert "additionalContext" in res_post
        assert "MEMORY" in res_post["additionalContext"]

    def test_antigravity_adapter(self, test_setup):
        vault_dir = test_setup["vault_dir"]
        adapter = GeminiAntigravityAdapter(vault_dir)

        injected = adapter.handle_session_start(project_id="alpha-project")
        assert isinstance(injected, str)
        assert "MEMORY" in injected

        post_injected = adapter.handle_post_compaction(project_id="alpha-project")
        assert isinstance(post_injected, str)
        assert "MEMORY" in post_injected

    def test_codex_adapter(self, test_setup):
        vault_dir = test_setup["vault_dir"]
        adapter = CodexAdapter(vault_dir)

        res_post = adapter.handle_post_compaction(project_id="alpha-project")
        assert res_post["success"] is True
        assert "context_text" in res_post
        assert "MEMORY" in res_post["context_text"]

    def test_generic_cli_adapter(self, test_setup):
        vault_dir = test_setup["vault_dir"]
        adapter = GenericCLIAdapter(vault_dir)

        output_txt = adapter.handle_session_start(project_id="alpha-project")
        assert isinstance(output_txt, str)
        assert "MEMORY" in output_txt
