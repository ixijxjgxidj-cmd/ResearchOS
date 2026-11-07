"""Tests for environment variable resolution and deep storage health probe."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from researchos.config.settings import Settings
from researchos.interfaces.mcp.server import health_endpoint


def test_vault_root_environment_precedence(tmp_path: Path):
    explicit_vault = tmp_path / "explicit"
    env_primary = tmp_path / "primary"
    env_compat = tmp_path / "compat"

    # 1. Explicit argument has highest priority
    with patch.dict(os.environ, {"RESEARCH_VAULT_ROOT": str(env_primary), "VAULT_PATH": str(env_compat)}):
        res = Settings.discover_vault_root(explicit_vault)
        assert res == explicit_vault.resolve()

    # 2. RESEARCH_VAULT_ROOT takes precedence over VAULT_PATH
    with patch.dict(os.environ, {"RESEARCH_VAULT_ROOT": str(env_primary), "VAULT_PATH": str(env_compat)}):
        res = Settings.discover_vault_root()
        assert res == env_primary.resolve()

    # 3. VAULT_PATH fallback when primary is absent
    with patch.dict(os.environ, {"VAULT_PATH": str(env_compat)}, clear=True):
        res = Settings.discover_vault_root()
        assert res == env_compat.resolve()


def test_mcp_transport_and_port_precedence():
    # Transport resolution
    with patch.dict(os.environ, {"MCP_TRANSPORT": "sse"}):
        assert Settings.get_mcp_transport() == "sse"
        assert Settings.get_mcp_transport("stdio") == "stdio"

    # Port resolution: CLI arg > PORT > MCP_PORT > default 8000
    with patch.dict(os.environ, {"PORT": "9000", "MCP_PORT": "8500"}):
        assert Settings.get_mcp_port() == 9000
        assert Settings.get_mcp_port(7777) == 7777

    with patch.dict(os.environ, {"MCP_PORT": "8500"}, clear=True):
        assert Settings.get_mcp_port() == 8500


@pytest.mark.asyncio
async def test_deep_healthcheck_endpoint(tmp_path: Path):
    vault = tmp_path / "healthy_vault"
    vault.mkdir()

    with patch.dict(os.environ, {"RESEARCH_VAULT_ROOT": str(vault)}):
        response = await health_endpoint(None)
        assert response.status_code == 200
        # parse response body
        import json
        body = json.loads(response.body.decode())
        assert body["status"] == "healthy"
        assert body["storage_writable"] is True
