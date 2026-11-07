"""Pytest configuration and shared fixtures for ResearchOS Universal Memory test suite."""

from pathlib import Path

import pytest

from researchos.core.context_builder import ContextBuilder
from researchos.core.handoff_service import HandoffService
from researchos.core.memory_service import MemoryService
from researchos.core.project_service import ProjectService
from researchos.core.retrieval_service import RetrievalService


@pytest.fixture
def vault_dir(tmp_path: Path) -> Path:
    """Provides a clean temporary ResearchVault directory."""
    v_dir = tmp_path / "test_vault"
    v_dir.mkdir(parents=True, exist_ok=True)
    return v_dir


@pytest.fixture
def project_service(vault_dir: Path) -> ProjectService:
    return ProjectService(vault_dir)


@pytest.fixture
def memory_service(vault_dir: Path) -> MemoryService:
    return MemoryService(vault_dir)


@pytest.fixture
def retrieval_service(vault_dir: Path) -> RetrievalService:
    return RetrievalService(vault_dir)


@pytest.fixture
def context_builder(vault_dir: Path) -> ContextBuilder:
    return ContextBuilder(vault_dir)


@pytest.fixture
def handoff_service(vault_dir: Path) -> HandoffService:
    return HandoffService(vault_dir)
