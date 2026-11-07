"""Pytest configuration and shared fixtures for ResearchOS test suite."""

from pathlib import Path
import pytest

from researchos.services.artifact_service import ArtifactService
from researchos.services.audit_service import AuditService
from researchos.services.claim_service import ClaimService
from researchos.services.context_service import ContextService
from researchos.services.experiment_service import ExperimentService
from researchos.services.finding_service import FindingService
from researchos.services.handoff_service import HandoffService
from researchos.services.paper_service import PaperService
from researchos.services.project_service import ProjectService
from researchos.services.run_service import RunService


@pytest.fixture
def vault_dir(tmp_path: Path) -> Path:
    """Provides an initialized clean temporary ResearchVault."""
    v_dir = tmp_path / "test_vault"
    v_dir.mkdir(parents=True, exist_ok=True)
    p_svc = ProjectService(v_dir)
    p_svc.init_vault()
    return v_dir


@pytest.fixture
def project_service(vault_dir: Path) -> ProjectService:
    return ProjectService(vault_dir)


@pytest.fixture
def experiment_service(vault_dir: Path) -> ExperimentService:
    return ExperimentService(vault_dir)


@pytest.fixture
def run_service(vault_dir: Path) -> RunService:
    return RunService(vault_dir)


@pytest.fixture
def paper_service(vault_dir: Path) -> PaperService:
    return PaperService(vault_dir)


@pytest.fixture
def artifact_service(vault_dir: Path) -> ArtifactService:
    return ArtifactService(vault_dir)


@pytest.fixture
def finding_service(vault_dir: Path) -> FindingService:
    return FindingService(vault_dir)


@pytest.fixture
def claim_service(vault_dir: Path) -> ClaimService:
    return ClaimService(vault_dir)


@pytest.fixture
def context_service(vault_dir: Path) -> ContextService:
    return ContextService(vault_dir)


@pytest.fixture
def handoff_service(vault_dir: Path) -> HandoffService:
    return HandoffService(vault_dir)


@pytest.fixture
def audit_service(vault_dir: Path) -> AuditService:
    return AuditService(vault_dir)
