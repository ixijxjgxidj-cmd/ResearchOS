"""Research audit service for scientific integrity and evidence completeness."""

from pathlib import Path
from typing import Any

from researchos.core.enums import (
    ClaimStatus,
    ExperimentOutcome,
    ExperimentStatus,
    RunStatus,
)
from researchos.core.models import (
    Artifact,
    Claim,
    Experiment,
    Finding,
    Paper,
    Project,
    Run,
    utc_now,
)
from researchos.services.artifact_service import ArtifactService
from researchos.storage.atomic_writer import atomic_write_text
from researchos.storage.markdown_store import MarkdownStore


class AuditService:
    """Verifies referential integrity, unverified claims, negative result preservation, and artifact hashes."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.store = MarkdownStore(self.vault_root)
        self.artifact_service = ArtifactService(self.vault_root)

    def run_audit(self, project_id: str | None = None) -> dict[str, Any]:
        issues: list[dict[str, str]] = []

        # 1. Load all entities
        projects: dict[str, Project] = {}
        experiments: dict[str, Experiment] = {}
        runs: dict[str, Run] = {}
        papers: dict[str, Paper] = {}
        claims: dict[str, Claim] = {}
        findings: dict[str, Finding] = {}
        artifacts: dict[str, Artifact] = {}

        # Papers
        lit_dir = self.vault_root / "01-Literature"
        if lit_dir.exists():
            for f in lit_dir.glob("*.md"):
                try:
                    p, _ = self.store.load_entity(f, Paper)
                    papers[p.id] = p
                except Exception as exc:
                    issues.append({"level": "ERROR", "entity": f.name, "message": f"Malformed paper file: {exc}"})

        # Projects and child entities
        projects_dir = self.vault_root / "00-Projects"
        if projects_dir.exists():
            for p_dir in projects_dir.iterdir():
                if not p_dir.is_dir():
                    continue
                proj_md = p_dir / "PROJECT.md"
                if not proj_md.exists():
                    issues.append({"level": "WARNING", "entity": p_dir.name, "message": "Project directory without PROJECT.md."})
                    continue
                try:
                    proj, _ = self.store.load_entity(proj_md, Project)
                    if project_id is not None and proj.id != project_id:
                        continue
                    projects[proj.id] = proj
                except Exception as exc:
                    issues.append({"level": "ERROR", "entity": proj_md.name, "message": f"Malformed project file: {exc}"})
                    continue

                # Load child entities
                for exp_f in (p_dir / "Experiments").glob("*.md"):
                    try:
                        exp, _ = self.store.load_entity(exp_f, Experiment)
                        experiments[exp.id] = exp
                    except Exception as exc:
                        issues.append({"level": "ERROR", "entity": exp_f.name, "message": f"Malformed experiment: {exc}"})

                for run_f in (p_dir / "Runs").glob("*.md"):
                    try:
                        r, _ = self.store.load_entity(run_f, Run)
                        runs[r.id] = r
                    except Exception as exc:
                        issues.append({"level": "ERROR", "entity": run_f.name, "message": f"Malformed run: {exc}"})

                for claim_f in (p_dir / "Claims").glob("*.md"):
                    try:
                        c, _ = self.store.load_entity(claim_f, Claim)
                        claims[c.id] = c
                    except Exception as exc:
                        issues.append({"level": "ERROR", "entity": claim_f.name, "message": f"Malformed claim: {exc}"})

                for find_f in (p_dir / "Findings").glob("*.md"):
                    try:
                        fd, _ = self.store.load_entity(find_f, Finding)
                        findings[fd.id] = fd
                    except Exception as exc:
                        issues.append({"level": "ERROR", "entity": find_f.name, "message": f"Malformed finding: {exc}"})

                for art_f in (p_dir / "Artifacts").glob("*.md"):
                    try:
                        art, _ = self.store.load_entity(art_f, Artifact)
                        artifacts[art.id] = art
                    except Exception as exc:
                        issues.append({"level": "ERROR", "entity": art_f.name, "message": f"Malformed artifact: {exc}"})

        # 2. Check referential integrity
        for exp_id, exp in experiments.items():
            if exp.project_id not in projects:
                issues.append({"level": "ERROR", "entity": exp_id, "message": f"Orphan experiment: Project '{exp.project_id}' does not exist."})
            for r_id in exp.runs:
                if r_id not in runs:
                    issues.append({"level": "ERROR", "entity": exp_id, "message": f"Dangling run reference: '{r_id}' not found."})
            for p_id in exp.literature:
                if p_id not in papers:
                    issues.append({"level": "WARNING", "entity": exp_id, "message": f"Dangling paper reference: '{p_id}' not in 01-Literature."})

        for r_id, r in runs.items():
            if r.experiment_id not in experiments:
                issues.append({"level": "ERROR", "entity": r_id, "message": f"Orphan run: Experiment '{r.experiment_id}' does not exist."})
            for art_id in r.artifacts:
                if art_id not in artifacts:
                    issues.append({"level": "WARNING", "entity": r_id, "message": f"Run references unindexed artifact: '{art_id}'."})

        # 3. Check claims evidence
        for claim_id, claim in claims.items():
            if claim.status == ClaimStatus.SUPPORTED and not claim.supporting_experiments and not claim.supporting_runs:
                issues.append({
                    "level": "ERROR",
                    "entity": claim_id,
                    "message": "Claim marked 'supported' without any supporting experiments or runs.",
                })
            for exp_ref in claim.supporting_experiments:
                if exp_ref not in experiments:
                    issues.append({"level": "ERROR", "entity": claim_id, "message": f"Claim references non-existent supporting experiment '{exp_ref}'."})

        # 4. Check negative results preservation
        negative_exps = [e for e in experiments.values() if e.outcome == ExperimentOutcome.NEGATIVE]
        all_contradicting_refs = {c_ref for clm in claims.values() for c_ref in clm.contradicting_experiments}
        for n_exp in negative_exps:
            if n_exp.id not in all_contradicting_refs:
                issues.append({
                    "level": "INFO",
                    "entity": n_exp.id,
                    "message": f"Negative outcome in experiment '{n_exp.id}' is not yet cited as contradicting evidence or limitation in any Claim.",
                })

        # 5. Check artifact hashes for local artifacts
        for art_id, art in artifacts.items():
            if art.storage_backend == "local":
                p = Path(art.path)
                if not p.is_file():
                    issues.append({"level": "WARNING", "entity": art_id, "message": f"Local artifact file missing at '{art.path}'."})
                else:
                    ver = self.artifact_service.verify_artifact(art.id)
                    if not ver.get("match", False):
                        issues.append({
                            "level": "ERROR",
                            "entity": art_id,
                            "message": f"Artifact hash mismatch! Recorded '{art.sha256[:10]}...', current '{ver.get('current_sha256', '')[:10]}...'.",
                        })

        # 6. Generate 99-Dashboard/Research-Audit.md
        dash_dir = self.vault_root / "99-Dashboard"
        dash_dir.mkdir(parents=True, exist_ok=True)

        lines = [
            "# Research Audit Report",
            f"*Generated: {utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}*",
            "",
            f"**Total Issues Detected**: {len(issues)}",
            "",
            "| Severity | Entity | Issue Description |",
            "|---|---|---|",
        ]
        if issues:
            for item in issues:
                lines.append(f"| `{item['level']}` | `{item['entity']}` | {item['message']} |")
        else:
            lines.append("| `OK` | Vault | All referential links, claims, and artifact hashes verified successfully. |")
        lines.append("")

        atomic_write_text(dash_dir / "Research-Audit.md", "\n".join(lines) + "\n")

        error_count = sum(1 for i in issues if i["level"] == "ERROR")
        warning_count = sum(1 for i in issues if i["level"] == "WARNING")
        return {
            "status": "passed" if error_count == 0 else "failed",
            "errors": error_count,
            "warnings": warning_count,
            "issues": issues,
            "report_path": str(dash_dir / "Research-Audit.md"),
        }
