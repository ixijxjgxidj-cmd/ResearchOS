"""Tests for Lite vs Advanced MCP Profile tool exposure and dynamic switching."""

import pytest
from researchos.config.settings import Settings
from researchos.interfaces.mcp.server import (
    LITE_TOOL_NAMES,
    _ALL_REGISTERED_TOOLS,
    apply_mcp_profile,
    mcp,
)


def test_settings_mcp_profile_precedence(monkeypatch):
    # Default is lite
    monkeypatch.delenv("RESEARCHOS_PROFILE", raising=False)
    monkeypatch.delenv("MCP_PROFILE", raising=False)
    assert Settings.get_mcp_profile(None) == "lite"

    # Environment variable
    monkeypatch.setenv("RESEARCHOS_PROFILE", "advanced")
    assert Settings.get_mcp_profile(None) == "advanced"

    # Argument overrides environment variable
    assert Settings.get_mcp_profile("lite") == "lite"

    monkeypatch.delenv("RESEARCHOS_PROFILE", raising=False)
    monkeypatch.setenv("MCP_PROFILE", "advanced")
    assert Settings.get_mcp_profile(None) == "advanced"


def test_lite_profile_tool_names():
    expected_lite = {
        "project_get",
        "context_build",
        "memory_add",
        "memory_search",
        "memory_get",
        "handoff_create",
    }
    assert LITE_TOOL_NAMES == expected_lite


def test_lite_profile_exposes_exactly_six_tools():
    # Apply Lite profile
    apply_mcp_profile(mcp, "lite")
    exposed_tools = set(mcp._tool_manager._tools.keys())

    assert len(exposed_tools) == 6
    assert exposed_tools == LITE_TOOL_NAMES

    # Ensure advanced/maintenance tools are not exposed
    assert "memory_supersede" not in exposed_tools
    assert "index_rebuild" not in exposed_tools
    assert "project_create" not in exposed_tools
    assert "project_memory_update" not in exposed_tools
    assert "paper_evidence_coverage" not in exposed_tools


def test_advanced_profile_preserves_all_tools():
    # Apply Advanced profile
    apply_mcp_profile(mcp, "advanced")
    exposed_tools = set(mcp._tool_manager._tools.keys())

    assert len(exposed_tools) >= 21
    assert "project_get" in exposed_tools
    assert "context_build" in exposed_tools
    assert "memory_add" in exposed_tools
    assert "memory_search" in exposed_tools
    assert "memory_get" in exposed_tools
    assert "handoff_create" in exposed_tools
    assert "memory_supersede" in exposed_tools
    assert "index_rebuild" in exposed_tools
    assert "paper_evidence_inventory" in exposed_tools
    assert "paper_evidence_coverage" in exposed_tools


def test_dynamic_profile_switching():
    # Switch to lite
    apply_mcp_profile(mcp, "lite")
    assert len(mcp._tool_manager._tools) == 6

    # Switch to advanced
    apply_mcp_profile(mcp, "advanced")
    assert len(mcp._tool_manager._tools) == len(_ALL_REGISTERED_TOOLS)

    # Switch back to lite
    apply_mcp_profile(mcp, "lite")
    assert len(mcp._tool_manager._tools) == 6
    assert set(mcp._tool_manager._tools.keys()) == LITE_TOOL_NAMES
