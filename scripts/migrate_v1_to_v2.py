"""Migration script to safely transition ResearchOS v1 vaults to v2 Universal Memory.

Features:
- Default Dry-Run mode (--apply required to write).
- Automated pre-migration snapshot backup.
- Conversion of Findings, Claims, Experiments, Runs, Papers, Decisions, and Artifacts to Universal Memory.
- Generates detailed Markdown & JSON migration audit report.
- Zero silent deletions: preserves all original raw data.
"""

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from researchos.core.storage_service import (
    atomic_write_text,
    dump_frontmatter,
    parse_frontmatter,
)
from researchos.models.memory import (
    MemoryFrontmatter,
    MemoryStatus,
    MemoryType,
    ProjectFrontmatter,
    utc_now,
)


def run_migration(
    vault_root: Path,
    target_root: Path | None = None,
    apply: bool = False,
    backup_dir: Path | None = None,
) -> dict[str, Any]:
    vault = vault_root.resolve()
    target = (target_root or vault).resolve()
    now_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    report: dict[str, Any] = {
        "timestamp": now_str,
        "vault_source": str(vault),
        "target_vault": str(target),
        "dry_run": not apply,
        "backup_path": None,
        "projects_migrated": [],
        "entities_migrated": {
            "projects": 0,
            "observations": 0,
            "knowledge": 0,
            "decisions": 0,
            "hypotheses": 0,
            "references": 0,
        },
        "errors": [],
    }

    old_projects_dir = vault / "00-Projects"
    if not old_projects_dir.exists():
        report["errors"].append(f"No '00-Projects' directory found at {vault}. Nothing to migrate.")
        return report

    # 1. Pre-migration backup
    if apply:
        b_dir = (backup_dir or (vault / f".backup_v1_{now_str}")).resolve()
        shutil.copytree(old_projects_dir, b_dir / "00-Projects", dirs_exist_ok=True)
        lit_dir = vault / "01-Literature"
        if lit_dir.exists():
            shutil.copytree(lit_dir, b_dir / "01-Literature", dirs_exist_ok=True)
        report["backup_path"] = str(b_dir)

    # 2. Collect global literature
    global_papers: list[tuple[dict[str, Any], str, Path]] = []
    lit_dir = vault / "01-Literature"
    if lit_dir.exists():
        for pf in sorted(lit_dir.glob("*.md")):
            try:
                meta, body = parse_frontmatter(pf.read_text(encoding="utf-8"))
                global_papers.append((meta, body, pf))
            except Exception as e:
                report["errors"].append(f"Failed parsing paper {pf.name}: {e}")

    # 3. Process each old project
    for p_dir in sorted(old_projects_dir.iterdir()):
        if not p_dir.is_dir() or p_dir.name.startswith("."):
            continue

        proj_file = p_dir / "PROJECT.md"
        if not proj_file.exists():
            continue

        pid = p_dir.name
        proj_meta, proj_body = parse_frontmatter(proj_file.read_text(encoding="utf-8"))
        p_name = proj_meta.get("name", pid)

        target_proj_dir = target / pid
        report["projects_migrated"].append(pid)
        report["entities_migrated"]["projects"] += 1

        if not apply:
            # Dry run: just tally entities
            for sub in ("Findings", "Runs", "Experiments", "Claims", "Decisions", "Artifacts"):
                sub_p = p_dir / sub
                if sub_p.exists():
                    cnt = len(list(sub_p.glob("*.md")))
                    if sub in ("Findings", "Runs", "Experiments"):
                        report["entities_migrated"]["observations"] += cnt
                    elif sub == "Claims":
                        report["entities_migrated"]["knowledge"] += cnt
                    elif sub == "Decisions":
                        report["entities_migrated"]["decisions"] += cnt
                    elif sub == "Artifacts":
                        report["entities_migrated"]["references"] += cnt
            continue

        # Real migration execution
        for sub in ("knowledge", "decisions", "hypotheses", "observations", "negative", "references", "handoffs", "archive"):
            (target_proj_dir / sub).mkdir(parents=True, exist_ok=True)

        # Migrate PROJECT.md
        now = utc_now()
        new_proj_fm = ProjectFrontmatter(
            project_id=pid,
            project_name=p_name,
            description=proj_meta.get("scope") or f"Migrated project: {p_name}",
            research_goal=proj_meta.get("research_question") or "Migrated research goal",
            created_at=now,
            updated_at=now,
            status=proj_meta.get("status", "active"),
            tags=proj_meta.get("objectives", []),
        )
        atomic_write_text(
            target_proj_dir / "PROJECT.md",
            dump_frontmatter(new_proj_fm.model_dump(mode="json"), proj_body),
        )

        # Migrate STATE.md
        old_status = p_dir / "STATUS.md"
        state_body = old_status.read_text(encoding="utf-8") if old_status.exists() else f"# State: {p_name}\n"
        atomic_write_text(target_proj_dir / "STATE.md", state_body)

        # Migrate HANDOFF.md
        old_handoff = p_dir / "HANDOFF.md"
        handoff_body = old_handoff.read_text(encoding="utf-8") if old_handoff.exists() else f"# Handoff: {p_name}\n"
        atomic_write_text(target_proj_dir / "HANDOFF.md", handoff_body)

        # Helper to convert and write memory
        mem_counter = 1000

        def convert_and_write(
            old_meta: dict[str, Any],
            body: str,
            m_type: MemoryType,
            sub_folder: str,
            source_id: str,
        ) -> None:
            nonlocal mem_counter
            mem_counter += 1
            mem_id = f"MEM-{now.year}-{mem_counter:04d}"
            title = old_meta.get("title") or old_meta.get("name") or old_meta.get("text") or source_id
            tags = old_meta.get("tags") or []
            if isinstance(tags, str):
                tags = [tags]

            fm = MemoryFrontmatter(
                id=mem_id,
                project_id=pid,
                type=m_type,
                title=str(title)[:100],
                created_at=now,
                updated_at=now,
                status=MemoryStatus.ACTIVE,
                source_agent=old_meta.get("agent_name", "migrator"),
                source_skill="migrate_v1_to_v2",
                source_ref=source_id,
                confidence=0.9,
                tags=tags,
                related=[],
                supersedes=None,
            )
            dest = target_proj_dir / sub_folder / f"{mem_id}.md"
            atomic_write_text(dest, dump_frontmatter(fm.model_dump(mode="json"), body))

        # Migrate Findings -> observations
        find_dir = p_dir / "Findings"
        if find_dir.exists():
            for f in sorted(find_dir.glob("*.md")):
                meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
                convert_and_write(meta, body, MemoryType.OBSERVATION, "observations", f.stem)
                report["entities_migrated"]["observations"] += 1

        # Migrate Runs -> observations
        runs_dir = p_dir / "Runs"
        if runs_dir.exists():
            for f in sorted(runs_dir.glob("*.md")):
                meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
                convert_and_write(meta, body, MemoryType.OBSERVATION, "observations", f.stem)
                report["entities_migrated"]["observations"] += 1

        # Migrate Experiments -> hypotheses or observations
        exp_dir = p_dir / "Experiments"
        if exp_dir.exists():
            for f in sorted(exp_dir.glob("*.md")):
                meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
                convert_and_write(meta, body, MemoryType.HYPOTHESIS, "hypotheses", f.stem)
                report["entities_migrated"]["hypotheses"] += 1

        # Migrate Claims -> knowledge
        claim_dir = p_dir / "Claims"
        if claim_dir.exists():
            for f in sorted(claim_dir.glob("*.md")):
                meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
                convert_and_write(meta, body, MemoryType.KNOWLEDGE, "knowledge", f.stem)
                report["entities_migrated"]["knowledge"] += 1

        # Migrate Decisions -> decisions
        dec_dir = p_dir / "Decisions"
        if dec_dir.exists():
            for f in sorted(dec_dir.glob("*.md")):
                meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
                convert_and_write(meta, body, MemoryType.DECISION, "decisions", f.stem)
                report["entities_migrated"]["decisions"] += 1

        # Migrate Artifacts -> references
        art_dir = p_dir / "Artifacts"
        if art_dir.exists():
            for f in sorted(art_dir.glob("*.md")):
                meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
                convert_and_write(meta, body, MemoryType.REFERENCE, "references", f.stem)
                report["entities_migrated"]["references"] += 1

        # Migrate referenced Literature -> references
        for p_meta, p_body, pf in global_papers:
            proj_refs = p_meta.get("projects", [])
            if pid in proj_refs or not proj_refs:
                convert_and_write(p_meta, p_body, MemoryType.REFERENCE, "references", pf.stem)
                report["entities_migrated"]["references"] += 1

        # Rebuild INDEX.md
        from researchos.core.project_service import ProjectService
        ps = ProjectService(target)
        ps.rebuild_index(pid)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="ResearchOS v1 to v2 Universal Memory Migration Tool")
    parser.add_argument("--vault", default=".", help="Root of v1 vault")
    parser.add_argument("--target", default=None, help="Root for migrated v2 vault (defaults to in-place/same)")
    parser.add_argument("--apply", action="store_true", help="Execute real migration (default is dry-run)")
    parser.add_argument("--backup-dir", default=None, help="Custom directory for backup")
    parser.add_argument("--json", action="store_true", help="Output report as JSON")
    args = parser.parse_args()

    vault_path = Path(args.vault).resolve()
    target_path = Path(args.target).resolve() if args.target else None
    backup_path = Path(args.backup_dir).resolve() if args.backup_dir else None

    report = run_migration(
        vault_root=vault_path,
        target_root=target_path,
        apply=args.apply,
        backup_dir=backup_path,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=" * 60)
        print("ResearchOS v1 -> v2 Migration Report")
        print("=" * 60)
        print(f"Mode: {'APPLY (Real Migration)' if args.apply else 'DRY-RUN (No changes applied)'}")
        print(f"Source Vault: {report['vault_source']}")
        print(f"Target Vault: {report['target_vault']}")
        if report["backup_path"]:
            print(f"Backup saved to: {report['backup_path']}")
        print("\nEntities Scanned/Migrated:")
        for k, v in report["entities_migrated"].items():
            print(f"  - {k}: {v}")
        if report["errors"]:
            print("\nWarnings/Errors:")
            for err in report["errors"]:
                print(f"  ! {err}")
        print("=" * 60)


if __name__ == "__main__":
    main()
