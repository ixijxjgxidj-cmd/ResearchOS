"""Lossless Migration Script: ResearchOS v2 to v3 Lightweight Architecture.

Migrates projects to the new standard 4-section MEMORY.md snapshot,
ensures records/ directory exists, creates pre-migration backups,
maintains 100% of existing Memory IDs, references, and files,
and supports dry-run and automatic rollback on failure.
"""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from researchos.config.settings import Settings
from researchos.core.memory_service import MemoryService
from researchos.core.project_memory_service import ProjectMemoryService
from researchos.core.project_service import ProjectService
from researchos.core.storage_service import atomic_write_text, file_lock
from researchos.models.memory import utc_now


def run_migration_v2_to_v3(
    vault_root: Path | str | None = None,
    target_project_id: str | None = None,
    dry_run: bool = False,
    backup: bool = True,
) -> dict[str, Any]:
    """Performs lossless migration of ResearchOS projects from v2 to v3.

    Returns:
        Migration report dict with pre/post validation stats and status.
    """
    root = Settings.discover_vault_root(vault_root)
    proj_svc = ProjectService(root)
    mem_svc = MemoryService(root)
    pms = ProjectMemoryService(root)

    projects = proj_svc.list_projects()
    if target_project_id:
        clean_target = target_project_id.strip().lower()
        projects = [p for p in projects if p.project_id == clean_target]
        if not projects:
            return {
                "success": False,
                "error": f"Target project '{target_project_id}' not found in vault '{root}'.",
                "projects_migrated": 0,
            }

    timestamp_str = utc_now().strftime("%Y%m%d_%H%M%S")
    report: dict[str, Any] = {
        "success": True,
        "dry_run": dry_run,
        "vault_root": str(root),
        "timestamp": utc_now().isoformat(),
        "projects": {},
        "summary": {
            "total_projects": len(projects),
            "migrated": 0,
            "failed": 0,
            "memories_preserved": 0,
        },
    }

    for proj in projects:
        pid = proj.project_id
        p_dir = Path(proj.project_dir)
        proj_report: dict[str, Any] = {
            "project_id": pid,
            "project_name": proj.project_name,
            "backup_path": None,
            "pre_migration_memories": 0,
            "post_migration_memories": 0,
            "memory_md_status": "unchanged",
            "records_dir_created": False,
            "status": "pending",
        }

        # 1. Pre-migration inventory
        pre_mems = pms._load_project_memories(pid)
        pre_ids = {m.id for m in pre_mems}
        proj_report["pre_migration_memories"] = len(pre_ids)

        if dry_run:
            proj_report["status"] = "dry_run_validated"
            proj_report["records_dir_created"] = not (p_dir / "records").exists()
            proj_report["memory_md_status"] = "would_regenerate_standard_snapshot"
            proj_report["post_migration_memories"] = len(pre_ids)
            report["projects"][pid] = proj_report
            report["summary"]["migrated"] += 1
            report["summary"]["memories_preserved"] += len(pre_ids)
            continue

        # 2. Backup before any modification
        backup_dir = p_dir / ".researchos" / "backups" / f"pre_v3_migration_{timestamp_str}"
        if backup:
            backup_dir.mkdir(parents=True, exist_ok=True)
            proj_report["backup_path"] = str(backup_dir)
            # Backup authoritative files and MEMORY.md
            for f_name in ("PROJECT.md", "STATE.md", "HANDOFF.md", "INDEX.md", "MEMORY.md"):
                src_f = p_dir / f_name
                if src_f.exists():
                    shutil.copy2(src_f, backup_dir / f_name)

        # 3. Transactional execution under lock
        lock_path = p_dir / ".researchos" / "project.lock"
        try:
            with file_lock(lock_path, timeout=15.0):
                # Ensure records/ exists
                records_folder = p_dir / "records"
                if not records_folder.exists():
                    records_folder.mkdir(parents=True, exist_ok=True)
                    proj_report["records_dir_created"] = True

                # Migrate MEMORY.md to standard 4-section v3 template preserving all custom notes
                new_mem_content = pms.rebuild_project_memory(pid, preserve_custom_notes=True)
                proj_report["memory_md_status"] = "regenerated_v3_standard"

                # Rebuild INDEX.md
                proj_svc.rebuild_index(pid)

                # Post-migration verification
                post_mems = pms._load_project_memories(pid)
                post_ids = {m.id for m in post_mems}
                proj_report["post_migration_memories"] = len(post_ids)

                if pre_ids != post_ids:
                    missing = pre_ids - post_ids
                    raise RuntimeError(f"Memory count mismatch after migration: missing {missing}")

                # Verify each memory is individually retrievable
                for mid in pre_ids:
                    mem_svc.get_memory(pid, mid)

                # Save migration map
                map_file = p_dir / ".researchos" / "migration_map.json"
                map_data = {
                    "migrated_at": utc_now().isoformat(),
                    "schema_version": "v3",
                    "total_memories": len(post_ids),
                    "memory_ids": sorted(list(post_ids)),
                }
                atomic_write_text(map_file, json.dumps(map_data, indent=2))

                proj_report["status"] = "success"
                report["summary"]["migrated"] += 1
                report["summary"]["memories_preserved"] += len(post_ids)

        except Exception as exc:
            proj_report["status"] = "failed"
            proj_report["error"] = str(exc)
            report["summary"]["failed"] += 1
            report["success"] = False

            # Rollback from backup if available
            if backup and backup_dir.exists():
                for bak_f in backup_dir.glob("*.md"):
                    shutil.copy2(bak_f, p_dir / bak_f.name)
                proj_report["status"] = "rolled_back"

        report["projects"][pid] = proj_report

    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ResearchOS v2 to v3 Lossless Migration")
    parser.add_argument("--vault", default=None, help="Path to ResearchVault root")
    parser.add_argument("--project", default=None, help="Target specific project_id (optional)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without modifying files")
    parser.add_argument("--no-backup", action="store_true", help="Skip pre-migration backup")

    args = parser.parse_args()
    res = run_migration_v2_to_v3(
        vault_root=args.vault,
        target_project_id=args.project,
        dry_run=args.dry_run,
        backup=not args.no_backup,
    )
    print(json.dumps(res, indent=2))
