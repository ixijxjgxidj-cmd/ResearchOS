"""Comprehensive test suite for audit hardening items 2, 3, 4, and 5.

Verifies:
- Item 2: Fine-grained concurrency in add_memory without lock starvation.
- Item 3: Windows NTFS case normalization and symlink escape defense.
- Item 4: Protection of scientific ML tokens, hashes, and commits from false-positive redaction.
- Item 5: MEMORY.md loss prevention, automatic backups (.bak), and section-by-section merge.
"""

import concurrent.futures
from pathlib import Path

import pytest

from researchos.core.memory_service import MemoryService
from researchos.core.project_memory_service import ProjectMemoryService
from researchos.core.project_service import ProjectService
from researchos.core.storage_service import validate_path_within
from researchos.models.memory import MemoryType
from researchos.utils.exceptions import PathSecurityError
from researchos.utils.sanitizer import (
    is_scientific_whitelisted_key,
    sanitize_markdown_text,
)

# =========================================================================
# Item 2: Concurrency & Fine-Grained Locking
# =========================================================================

def test_concurrent_add_memory_fine_grained_locking(tmp_path: Path):
    """Verifies that multiple concurrent agents can call add_memory simultaneously without lock contention."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Concurrent Memory Test", project_id="conc-test")
    ms = MemoryService(vault)

    num_workers = 10
    memories_per_worker = 3

    def worker_task(worker_id: int):
        created_ids = []
        for i in range(memories_per_worker):
            mem = ms.add_memory(
                project_id="conc-test",
                type=MemoryType.OBSERVATION,
                title=f"Worker {worker_id} Observation #{i}",
                content=f"Detailed empirical log data from worker thread {worker_id} iteration {i}.",
                tags=["concurrent", f"worker-{worker_id}"],
            )
            created_ids.append(mem.id)
        return created_ids

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker_task, w) for w in range(num_workers)]
        all_results = [f.result() for f in futures]

    total_created = [mid for worker_ids in all_results for mid in worker_ids]
    assert len(total_created) == num_workers * memories_per_worker
    # Ensure all generated IDs are strictly unique
    assert len(set(total_created)) == len(total_created)

    # Check that INDEX.md is intact and includes all memories
    idx_content = (vault / "conc-test" / "INDEX.md").read_text(encoding="utf-8")
    assert f"Active Memories**: `{len(total_created)}`" in idx_content


# =========================================================================
# Item 3: Windows NTFS Case-Insensitivity & Symlink Escape Defense
# =========================================================================

def test_project_id_case_normalization(tmp_path: Path):
    """Verifies that project_ids are canonicalized to lowercase, preventing Windows NTFS directory collisions."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    p1 = ps.create_project("Seismic JEPA", project_id="JEPA-Seismic")

    assert p1.project_id == "jepa-seismic"
    assert (vault / "jepa-seismic").exists()

    # Querying with mixed/uppercase returns the exact same project directory
    p_dir_mixed = ps.get_project_dir("JEPa-Seismic")
    p_dir_upper = ps.get_project_dir("JEPA-SEISMIC")
    assert p_dir_mixed == p_dir_upper
    assert p_dir_mixed == vault / "jepa-seismic"


def test_validate_path_within_symlink_escape_detection(tmp_path: Path):
    """Verifies that validate_path_within detects symlink escapes and path traversal."""
    root_dir = tmp_path / "safe_root"
    root_dir.mkdir()
    outside_dir = tmp_path / "outside_danger"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.txt"
    secret_file.write_text("classified", encoding="utf-8")

    # 1. Normal safe file within root
    safe_file = root_dir / "safe.txt"
    safe_file.write_text("hello", encoding="utf-8")
    validated = validate_path_within(root_dir, safe_file)
    assert validated == safe_file.resolve()

    # 2. Path traversal attack
    traversal_path = root_dir / ".." / "outside_danger" / "secret.txt"
    with pytest.raises(PathSecurityError, match="escapes base directory"):
        validate_path_within(root_dir, traversal_path)

    # 3. Symlink escape (if platform supports symlinks)
    symlink_path = root_dir / "link_to_outside"
    try:
        symlink_path.symlink_to(outside_dir, target_is_directory=True)
        with pytest.raises(PathSecurityError, match="escapes base directory"):
            validate_path_within(root_dir, symlink_path / "secret.txt")
    except (OSError, NotImplementedError):
        # Platform privilege might restrict symlinks on Windows non-admin, skip symlink test
        pass


# =========================================================================
# Item 4: False-Positive Secret Redaction Protection
# =========================================================================

def test_scientific_keys_whitelisted():
    """Verifies that ML/NLP token parameters are not treated as credentials."""
    assert is_scientific_whitelisted_key("pad_token")
    assert is_scientific_whitelisted_key("mask_token")
    assert is_scientific_whitelisted_key("special_tokens")
    assert is_scientific_whitelisted_key("token_type_ids")
    assert is_scientific_whitelisted_key("bos_token")
    assert is_scientific_whitelisted_key("eos_token")
    assert is_scientific_whitelisted_key("unk_token")

    # Real secret keys must NOT be whitelisted
    assert not is_scientific_whitelisted_key("auth_token")
    assert not is_scientific_whitelisted_key("api_key")
    assert not is_scientific_whitelisted_key("jwt_token")
    assert not is_scientific_whitelisted_key("access_token")
    assert not is_scientific_whitelisted_key("secret_token")


def test_scientific_hashes_and_tokens_preserved():
    """Verifies that scientific hashes, git commits, and ML configurations are preserved in markdown."""
    text_with_science_and_secrets = """
# Model Training Run Summary

## Model Configurations
- `pad_token`: "[PAD]"
- `mask_token`: "[MASK]"
- `token_type_ids`: torch.zeros((batch, seq_len))
- Checkpoint SHA256: 7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069
- Git Commit: 4a3f2b1c9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b

## Secret Leak (Should be redacted)
- OpenAI API Key: sk-proj-1234567890abcdef1234567890abcdef
- Password: password=MySecretPass123!
"""
    sanitized = sanitize_markdown_text(text_with_science_and_secrets)

    # Scientific properties MUST remain intact
    assert "pad_token" in sanitized
    assert "mask_token" in sanitized
    assert "token_type_ids" in sanitized
    assert "7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069" in sanitized
    assert "4a3f2b1c9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b" in sanitized

    # Credentials MUST be redacted
    assert "sk-proj-" not in sanitized
    assert "MySecretPass123!" not in sanitized
    assert "[REDACTED_CREDENTIAL]" in sanitized


# =========================================================================
# Item 5: MEMORY.md Loss Prevention & Intelligent Note Merging
# =========================================================================

def test_memory_md_backup_and_merge_preserves_custom_notes(tmp_path: Path):
    """Verifies that rebuilding MEMORY.md preserves custom notes and creates backups."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Preservation Project", project_id="preserve-proj")
    ms = MemoryService(vault)
    pms = ProjectMemoryService(vault)

    # 1. Initially generated MEMORY.md exists
    mem_file = pms.get_memory_file("preserve-proj")
    assert mem_file.exists()

    # 2. Agent/human updates MEMORY.md with rich custom domain notes
    custom_content = """# Always-on Project Memory: Preservation Project
*Project ID: `preserve-proj` | Last Updated: 2026-11-08T00:00:00*

> [!IMPORTANT]
> Executive summary.

## 1. Project Identity
- **Research Topic**: Preservation Project
- **Core Goal**: Develop self-supervised foundation models for sub-surface imaging.
- **Description**: Pre-training Vision Transformers on unlabelled 3D seismic cubes.
- **Target Publication Venue**: IEEE TGRS 2026 (Major Target)
- Note: Primary grant funding under NSFC-6237001.

## 2. Core Research Idea
- Pre-training Vision Transformers on unlabelled 3D seismic cubes.
- **Key Innovations**: Latent mask predictive coding applied to 3D seismic dip azimuths.
- **Difference from Prior Work**: Replaces pixel-level reconstruction with high-level latent feature prediction.
- Custom Theoretical Insight: Seismic waveforms exhibit anisotropic frequency attenuation.

## 3. Confirmed Findings
- _No confirmed empirical findings recorded yet._

## 4. Current Hypotheses
- _No active hypotheses recorded yet._

## 5. Important Decisions
- _No major architectural decisions recorded._

## 6. Current Research Status
- **Current Milestone**: Completed synthetic dataset pre-processing pipeline.
- **Current Blocker**: GPU VRAM exhaustion on patch size 16x16x16 with batch size 64.

## 7. Paper Structure
- Section 1 (Introduction): Motivation from geological exploration limits.
- Section 3 (Methodology): 3D Latent Mask Encoder with Target Exponential Moving Average.
- Section 4 (Experiments): Downstream fault interpretation benchmark comparison.

## 8. Important Memory Pointers
- _None recorded yet._

## 9. Next Actions
1. Implement gradient checkpointing in 3D Transformer encoder.
2. Conduct 4-GPU distributed baseline validation.

## 10. Important Warnings
- > [!WARNING] Never use random crop without boundary padding on seismic border traces!
"""
    pms.update_project_memory("preserve-proj", custom_content)

    # Verify backup was created upon update
    bak_file = mem_file.with_name("MEMORY.md.bak")
    assert bak_file.exists()

    # 3. Add an empirical observation and negative finding
    obs = ms.add_memory(
        project_id="preserve-proj",
        type=MemoryType.OBSERVATION,
        title="Gradient Checkpointing Reduces Memory by 58%",
        content="Peak memory dropped from 74GB to 31GB per GPU.",
        source_ref="run-checkpoint-01",
    )
    neg = ms.add_memory(
        project_id="preserve-proj",
        type=MemoryType.NEGATIVE,
        title="Batch Size 128 Causes Sudden Divergence",
        content="Loss exploded at epoch 14.",
    )

    # 4. Trigger rebuild_project_memory with preserve_custom_notes=True
    rebuilt = pms.rebuild_project_memory("preserve-proj", preserve_custom_notes=True)

    # Verify timestamped backup in .researchos/backups/
    backups_dir = vault / "preserve-proj" / ".researchos" / "backups"
    assert backups_dir.exists()
    ts_backups = list(backups_dir.glob("MEMORY_*.md"))
    assert len(ts_backups) >= 1

    # Verify that newly created memories are integrated
    assert obs.id in rebuilt
    assert neg.id in rebuilt

    # Verify that custom manual notes across sections were preserved!
    # Section 1: Venue & grant note
    assert "IEEE TGRS 2026 (Major Target)" in rebuilt
    assert "NSFC-6237001" in rebuilt

    # Section 2: Innovations & difference & theoretical insight
    assert "Latent mask predictive coding applied to 3D seismic dip azimuths." in rebuilt
    assert "Replaces pixel-level reconstruction with high-level latent feature prediction." in rebuilt
    assert "anisotropic frequency attenuation" in rebuilt

    # Section 6: Current status notes
    assert "Completed synthetic dataset pre-processing pipeline." in rebuilt
    assert "GPU VRAM exhaustion on patch size" in rebuilt

    # Section 7: Custom paper structure
    assert "Motivation from geological exploration limits." in rebuilt
    assert "3D Latent Mask Encoder with Target Exponential Moving Average." in rebuilt

    # Section 9: Custom next actions
    assert "Implement gradient checkpointing in 3D Transformer encoder." in rebuilt
    assert "Conduct 4-GPU distributed baseline validation." in rebuilt

    # Section 10: Custom warning preserved alongside negative memory
    assert "Never use random crop without boundary padding" in rebuilt
    assert f"{neg.id}" in rebuilt


def test_memory_md_rebuild_force_clean_resets_template(tmp_path: Path):
    """Verifies that rebuild_project_memory with preserve_custom_notes=False resets to clean template."""
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Clean Reset Project", project_id="clean-proj")
    pms = ProjectMemoryService(vault)

    # Set custom content
    custom_content = """# Always-on Project Memory: Clean Reset Project
*Project ID: `clean-proj` | Last Updated: 2026-11-08T00:00:00*

## 1. Project Identity
- **Research Topic**: Clean Reset Project
- **Core Goal**: Old Goal
- **Description**: Old Desc
- **Target Publication Venue**: Old Venue 2024
"""
    pms.update_project_memory("clean-proj", custom_content)

    # Force clean rebuild
    rebuilt = pms.rebuild_project_memory("clean-proj", preserve_custom_notes=False)

    assert "Old Venue 2024" not in rebuilt
    assert "_Not yet established_" in rebuilt
    # But backup still preserved previous state!
    bak_content = (vault / "clean-proj" / "MEMORY.md.bak").read_text(encoding="utf-8")
    assert "Old Venue 2024" in bak_content
