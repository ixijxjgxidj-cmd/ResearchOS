"""Test G: Concurrency, optimistic locking, and conflict detection."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import pytest

from researchos.core.enums import IdPrefix
from researchos.core.exceptions import VersionConflictError
from researchos.core.ids import IdGenerator
from researchos.core.models import Project
from researchos.services.project_service import ProjectService
from researchos.storage.markdown_store import MarkdownStore


def test_concurrent_id_generation(vault_dir: Path):
    """Verifies that multiple concurrent agents allocating IDs receive unique, non-overlapping IDs."""
    num_threads = 10
    ids_per_thread = 5

    def generate_worker():
        gen = IdGenerator(vault_dir)
        return [gen.generate_id(IdPrefix.EXPERIMENT, year=2026) for _ in range(ids_per_thread)]

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(generate_worker) for _ in range(num_threads)]
        all_ids = []
        for f in futures:
            all_ids.extend(f.result())

    assert len(all_ids) == num_threads * ids_per_thread
    # Ensure zero duplicates
    assert len(set(all_ids)) == len(all_ids)


def test_optimistic_concurrency_conflict(vault_dir: Path, project_service: ProjectService):
    """Verifies that simultaneous file modifications with stale timestamps raise VersionConflictError."""
    proj = project_service.create_project(name="Concurrent Project")
    store = MarkdownStore(vault_dir)
    proj_path = store.resolve_entity_path(proj.id)

    # Agent A reads project
    entity_a, body_a = store.load_entity(proj_path, Project)
    orig_time = entity_a.updated_at

    # Agent B modifies and writes project first
    entity_b, body_b = store.load_entity(proj_path, Project)
    entity_b.name = "Project Modified by Agent B"
    store.save_entity(entity_b, body_b, path=proj_path)

    # Agent A tries to overwrite using its original timestamp
    entity_a.name = "Project Modified by Agent A"
    with pytest.raises(VersionConflictError) as exc_info:
        store.save_entity(entity_a, body_a, path=proj_path, expected_updated_at=orig_time)

    assert "Version conflict" in str(exc_info.value)
    assert exc_info.value.file_path == str(proj_path)
