"""Context Builder service for re-hydrating Agent memory without full chat history."""

from pathlib import Path
from typing import Any

from researchos.core.enums import (
    ExperimentStatus,
    IdPrefix,
)
from researchos.core.exceptions import (
    EntityNotFoundError,
    ValidationError,
)
from researchos.core.ids import validate_id
from researchos.core.models import (
    Decision,
    Experiment,
    Finding,
    Paper,
    Project,
    Run,
    utc_now,
)
from researchos.storage.link_resolver import format_markdown_link
from researchos.storage.markdown_store import MarkdownStore


class ContextService:
    """Extracts, filters, and packages essential research context for newly spawned Agents."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.store = MarkdownStore(self.vault_root)

    def build_context(self, target_id: str) -> str:
        """Constructs a deterministic Markdown Research Context Pack for an Experiment or Project."""
        prefix, _, _ = validate_id(target_id)

        target_exp: Experiment | None = None
        target_proj: Project | None = None
        project_id: str = ""

        if prefix == IdPrefix.EXPERIMENT:
            exp_path = self.store.resolve_entity_path(target_id)
            if not exp_path.exists():
                raise EntityNotFoundError(f"Experiment {target_id} not found.")
            target_exp, _ = self.store.load_entity(exp_path, Experiment)
            project_id = target_exp.project_id
            proj_path = self.store.resolve_entity_path(project_id)
            if proj_path.exists():
                target_proj, _ = self.store.load_entity(proj_path, Project)
        elif prefix == IdPrefix.PROJECT:
            project_id = target_id
            proj_path = self.store.resolve_entity_path(project_id)
            if not proj_path.exists():
                raise EntityNotFoundError(f"Project {target_id} not found.")
            target_proj, _ = self.store.load_entity(proj_path, Project)
        else:
            raise ValidationError(
                f"Context can only be built for Project (PRJ-*) or Experiment (EXP-*), got '{target_id}'."
            )

        if not target_proj:
            raise EntityNotFoundError(f"Parent project {project_id} could not be resolved.")

        proj_dir = self.store.get_project_dir(project_id)
        source_refs: list[str] = [f"00-Projects/{project_id}/PROJECT.md"]

        # Read STATUS.md & HANDOFF.md
        status_text = ""
        status_file = proj_dir / "STATUS.md"
        if status_file.exists():
            status_text = status_file.read_text(encoding="utf-8").strip()
            source_refs.append(f"00-Projects/{project_id}/STATUS.md")

        handoff_text = ""
        handoff_file = proj_dir / "HANDOFF.md"
        if handoff_file.exists():
            handoff_text = handoff_file.read_text(encoding="utf-8").strip()
            source_refs.append(f"00-Projects/{project_id}/HANDOFF.md")

        # Collect related experiments
        experiments: list[Experiment] = []
        exp_dir = proj_dir / "Experiments"
        if exp_dir.exists():
            for f in sorted(exp_dir.glob("*.md")):
                try:
                    e, _ = self.store.load_entity(f, Experiment)
                    experiments.append(e)
                    if target_exp and e.id == target_exp.id:
                        source_refs.append(f"00-Projects/{project_id}/Experiments/{e.id}.md")
                except Exception:
                    continue

        # Collect runs
        runs: list[Run] = []
        runs_dir = proj_dir / "Runs"
        if runs_dir.exists():
            for f in sorted(runs_dir.glob("*.md")):
                try:
                    r, _ = self.store.load_entity(f, Run)
                    # If target experiment, include its runs; otherwise include recent runs
                    if target_exp and r.experiment_id == target_exp.id:
                        runs.append(r)
                        source_refs.append(f"00-Projects/{project_id}/Runs/{r.id}.md")
                    elif not target_exp:
                        runs.append(r)
                except Exception:
                    continue

        # Collect literature
        papers: list[Paper] = []
        paper_ids = set(target_proj.literature)
        if target_exp:
            paper_ids.update(target_exp.literature)

        lit_dir = self.vault_root / "01-Literature"
        if lit_dir.exists():
            for pid in paper_ids:
                p_file = lit_dir / f"{pid}.md"
                if p_file.exists():
                    try:
                        p, _ = self.store.load_entity(p_file, Paper)
                        papers.append(p)
                        source_refs.append(f"01-Literature/{p.id}.md")
                    except Exception:
                        continue

        # Collect findings
        findings: list[Finding] = []
        findings_dir = proj_dir / "Findings"
        if findings_dir.exists():
            for f in sorted(findings_dir.glob("*.md")):
                try:
                    find, _ = self.store.load_entity(f, Finding)
                    if target_exp and find.experiment_id == target_exp.id:
                        findings.append(find)
                        source_refs.append(f"00-Projects/{project_id}/Findings/{find.id}.md")
                    elif not target_exp:
                        findings.append(find)
                except Exception:
                    continue

        # Collect decisions
        decisions: list[Decision] = []
        dec_dir = proj_dir / "Decisions"
        if dec_dir.exists():
            for f in sorted(dec_dir.glob("*.md")):
                try:
                    d, _ = self.store.load_entity(f, Decision)
                    decisions.append(d)
                    source_refs.append(f"00-Projects/{project_id}/Decisions/{d.id}.md")
                except Exception:
                    continue

        # Assemble the Markdown Context Pack
        lines: list[str] = [
            f"# Research Context Pack: {target_id}",
            f"*Generated by ResearchOS Context Builder at {utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}*",
            "",
            "## Current Project",
            f"- **Project ID**: `{target_proj.id}`",
            f"- **Name**: {target_proj.name}",
            f"- **Status**: `{target_proj.status.value}`",
            f"- **Core Research Question**: {target_proj.research_question or '[Not defined]'}",
            f"- **Objectives**: {', '.join(target_proj.objectives) if target_proj.objectives else '[None]'}",
            f"- **Repositories**: {', '.join(target_proj.repositories) if target_proj.repositories else '[None]'}",
            f"- **Source File**: `00-Projects/{target_proj.id}/PROJECT.md`",
            "",
        ]

        if target_exp:
            lines.extend([
                "## Current Task",
                f"- **Target Experiment**: `{target_exp.id}` - **{target_exp.title}**",
                f"- **Lifecycle Status**: `{target_exp.status.value}`",
                f"- **Outcome**: `{target_exp.outcome.value}`",
                f"- **Exploratory**: `{'Yes' if target_exp.is_exploratory else 'No'}`",
                f"- **Specific Research Question**: {target_exp.research_question or target_proj.research_question or '[None]'}",
                f"- **Scientific Hypothesis**: {target_exp.hypothesis or '[Exploratory / Unspecified]'}",
                f"- **Rationale**: {target_exp.rationale or '[None]'}",
                f"- **Execution Method**: {target_exp.method or '[None]'}",
                f"- **Planned Parameters (Plan)**: `{target_exp.planned_parameters}`",
                f"- **Expected Results**: {target_exp.expected_result or '[None]'}",
                f"- **Success Criteria**: {target_exp.success_criteria or '[None]'}",
                f"- **Execution Targets**: `{target_exp.execution}`",
                "",
            ])

        lines.extend([
            "## Required Reading",
            "Latest project state & handoff guidelines:",
            "",
            "### Recent Project Status",
            status_text if status_text else "_No STATUS.md present._",
            "",
            "### Agent Handoff Summary",
            handoff_text if handoff_text else "_No HANDOFF.md present._",
            "",
        ])

        # Related Experiments
        lines.append("## Related Experiments")
        if experiments:
            for exp in experiments:
                is_curr = " (CURRENT)" if target_exp and exp.id == target_exp.id else ""
                lines.append(
                    f"- `{exp.id}`{is_curr}: **{exp.title}** | Status: `{exp.status.value}` | Outcome: `{exp.outcome.value}`"
                )
        else:
            lines.append("_No experiments created in this project yet._")
        lines.append("")

        # Related Runs
        lines.append("## Related Runs")
        if runs:
            for r in runs:
                lines.append(
                    f"- `{r.id}` ({r.experiment_id}): Agent `{r.agent_name}` | Status: `{r.status.value}` | Actual Params: `{r.actual_parameters}` | Metrics: `{r.metrics}`"
                )
        else:
            lines.append("_No execution runs recorded yet._")
        lines.append("")

        # Literature
        lines.append("## Literature")
        if papers:
            for p in papers:
                lines.append(
                    f"- `{p.id}` (`{p.citekey}`): **{p.title}** ({p.year or 'n.d.'}) | Reading Status: `{p.reading_status.value}`"
                )
                if p.abstract:
                    lines.append(f"  > Abstract: {p.abstract[:200]}...")
        else:
            lines.append("_No linked literature._")
        lines.append("")

        # Existing Findings
        lines.append("## Existing Findings")
        if findings:
            for find in findings:
                lines.append(f"- `{find.id}`: **{find.title}** (Status: `{find.status.value}`)")
        else:
            lines.append("_No empirical findings registered yet._")
        lines.append("")

        # Important Decisions
        lines.append("## Important Decisions")
        if decisions:
            for dec in decisions:
                lines.append(f"- `{dec.id}`: **{dec.title}** (Author: `{dec.author}`) [{dec.date.strftime('%Y-%m-%d')}]")
        else:
            lines.append("_No major decisions recorded._")
        lines.append("")

        # Pending Work
        lines.append("## Pending Work")
        pending_exps = [e for e in experiments if e.status not in (ExperimentStatus.COMPLETED, ExperimentStatus.ABANDONED)]
        if pending_exps:
            for pe in pending_exps:
                lines.append(f"- [ ] Experiment `{pe.id}`: {pe.title} (Status: `{pe.status.value}`)")
        else:
            lines.append("- No pending experiments. Ready for new hypothesis or manuscript drafting.")
        lines.append("")

        # Warnings & Boundaries
        lines.append("## Warnings")
        warnings_found: list[str] = []
        for r in runs:
            if r.status == "failed":
                warnings_found.append(f"Run `{r.id}` failed: {r.errors or 'Check run logs'}")
        for e in experiments:
            if e.outcome == "negative":
                warnings_found.append(f"Experiment `{e.id}` yielded a NEGATIVE outcome. Do not ignore in claims.")

        if warnings_found:
            for w in warnings_found:
                lines.append(f"> [!WARNING]\n> {w}")
        else:
            lines.append("No active warnings or failed run blockers.")
        lines.append("")

        # Source References
        lines.append("## Source References")
        for ref in sorted(set(source_refs)):
            lines.append(f"- `{ref}`")
        lines.append("")

        return "\n".join(lines)
