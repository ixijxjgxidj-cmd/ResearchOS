"""Tests for atomic supersede transactions, bidirectional linkage, rollback, and revision protection."""

from pathlib import Path
from unittest.mock import patch

import pytest

from researchos.core.memory_service import MemoryService
from researchos.core.project_service import ProjectService
from researchos.models.memory import MemoryStatus, MemoryType
from researchos.utils.exceptions import ValidationError


def test_bidirectional_superseding(tmp_path: Path):
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Supersede Test", project_id="sup-proj")
    ms = MemoryService(vault)

    # 1. Create old memory
    old_mem = ms.add_memory(
        project_id="sup-proj",
        type=MemoryType.OBSERVATION,
        title="Initial ViT Learning Rate Baseline",
        content="LR 1e-3 works best with batch size 512.",
        tags=["vit", "lr"],
    )
    assert old_mem.status == MemoryStatus.ACTIVE
    assert old_mem.superseded_by is None

    # 2. Supersede old memory
    new_mem = ms.supersede_memory(
        project_id="sup-proj",
        old_memory_id=old_mem.id,
        title="Revised ViT Learning Rate: 3e-4 with Warmup",
        content="1e-3 causes training collapse at step 10k. 3e-4 is optimal with cosine schedule.",
        reason="Extended run to 100k steps revealed divergence at 1e-3.",
        tags=["vit", "lr", "schedule"],
    )

    # 3. Verify new memory
    assert new_mem.supersedes == old_mem.id
    assert new_mem.superseded_by is None
    assert new_mem.status == MemoryStatus.ACTIVE
    assert "revised" in new_mem.tags
    assert old_mem.id in new_mem.related

    # 4. Verify old memory state updated
    refreshed_old = ms.get_memory("sup-proj", old_mem.id)
    assert refreshed_old.status == MemoryStatus.SUPERSEDED
    assert refreshed_old.superseded_by == new_mem.id


def test_supersede_rollback_on_failure(tmp_path: Path):
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Rollback Test", project_id="rb-proj")
    ms = MemoryService(vault)

    orig_mem = ms.add_memory(
        project_id="rb-proj",
        type=MemoryType.DECISION,
        title="Architecture Decision: Pure CNN",
        content="We chose ConvNet over Transformer.",
    )

    # Simulate an error during atomic_write_text for the new memory
    with patch("researchos.core.memory_service.atomic_write_text", side_effect=[IOError("Simulated disk error!")]):
        with pytest.raises(IOError):
            ms.supersede_memory(
                project_id="rb-proj",
                old_memory_id=orig_mem.id,
                title="Shift to Vision Transformer",
                content="Transformers outperform CNN on ImageNet.",
                reason="Benchmark results.",
            )

    # Assert old memory was NOT corrupted or left in superseded state
    reloaded_orig = ms.get_memory("rb-proj", orig_mem.id)
    assert reloaded_orig.status == MemoryStatus.ACTIVE
    assert reloaded_orig.superseded_by is None


def test_prevent_content_overwrite_on_superseded_memory(tmp_path: Path):
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Protection Test", project_id="prot-proj")
    ms = MemoryService(vault)

    m1 = ms.add_memory(
        project_id="prot-proj",
        type=MemoryType.NEGATIVE,
        title="Failed Quantization Config",
        content="W4A4 leads to 40% perplexity degradation.",
    )

    # Supersede it
    ms.add_memory(
        project_id="prot-proj",
        type=MemoryType.OBSERVATION,
        title="W8A8 Success",
        content="W8A8 preserves accuracy.",
    )
    ms.supersede_memory(
        project_id="prot-proj",
        old_memory_id=m1.id,
        title="W4A8 Viable Solution",
        content="W4A8 works with weight-only quantization.",
        reason="Tested hybrid precision.",
    )

    # Attempting to overwrite content of superseded memory m1 directly must be rejected
    with pytest.raises(ValidationError, match="Cannot overwrite content of superseded memory"):
        ms.update_memory(
            project_id="prot-proj",
            memory_id=m1.id,
            content="Attempted rewrite of history.",
        )
