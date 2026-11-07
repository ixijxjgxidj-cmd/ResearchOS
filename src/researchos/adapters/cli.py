"""Command Line Interface for ResearchOS."""

import json
from pathlib import Path
from typing import Annotated, Any, Optional

from rich.console import Console
from rich.table import Table
import typer

from researchos.config.settings import Settings
from researchos.core.enums import (
    ArtifactRole,
    ExperimentOutcome,
    ExperimentStatus,
    PaperReadingStatus,
    RunStatus,
)
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

app = typer.Typer(name="research", help="ResearchOS: Autonomous Scientific Research Management Framework")
console = Console()
err_console = Console(stderr=True)

# Sub-command groups
project_app = typer.Typer(name="project", help="Manage research projects")
experiment_app = typer.Typer(name="experiment", help="Manage experiments and hypotheses")
run_app = typer.Typer(name="run", help="Manage execution runs and parameter isolation")
paper_app = typer.Typer(name="paper", help="Manage literature, citekeys, and reading notes")
artifact_app = typer.Typer(name="artifact", help="Register and verify execution artifacts")
context_app = typer.Typer(name="context", help="Build context packs for autonomous agents")
handoff_app = typer.Typer(name="handoff", help="Manage inter-agent context handoffs")

app.add_typer(project_app)
app.add_typer(experiment_app)
app.add_typer(run_app)
app.add_typer(paper_app)
app.add_typer(artifact_app)
app.add_typer(context_app)
app.add_typer(handoff_app)


def get_vault_path(vault: str | None) -> Path:
    return Settings.discover_vault_root(vault)


def output_result(data: Any, as_json: bool = False) -> None:
    if as_json:
        if hasattr(data, "model_dump"):
            console.print_json(data.model_dump_json(indent=2))
        elif isinstance(data, list) and data and hasattr(data[0], "model_dump"):
            console.print_json(json.dumps([x.model_dump(mode="json") for x in data], indent=2))
        else:
            console.print_json(json.dumps(data, indent=2, default=str))
    else:
        if isinstance(data, str):
            console.print(data)
        elif isinstance(data, dict):
            for k, v in data.items():
                console.print(f"[bold cyan]{k}:[/bold cyan] {v}")
        else:
            console.print(data)


# Top-level init
@app.command("init")
def init(
    vault: Annotated[Optional[str], typer.Option("--vault", "-v", help="Vault root directory")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Initializes a new ResearchVault filesystem structure."""
    v_path = get_vault_path(vault)
    svc = ProjectService(v_path)
    res = svc.init_vault()
    if as_json:
        output_result(res, as_json=True)
    else:
        console.print(f"[bold green]Vault initialized successfully at:[/bold green] {v_path}")


# Project commands
@project_app.command("create")
def project_create(
    name: Annotated[str, typer.Argument(help="Project title")],
    question: Annotated[Optional[str], typer.Option("--question", "-q", help="Core research question")] = None,
    objectives: Annotated[Optional[list[str]], typer.Option("--objective", "-o", help="Project objectives")] = None,
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Creates a new research project."""
    v_path = get_vault_path(vault)
    svc = ProjectService(v_path)
    proj = svc.create_project(name=name, research_question=question, objectives=objectives or [])
    if as_json:
        output_result(proj, as_json=True)
    else:
        console.print(f"[bold green]Created project {proj.id}:[/bold green] {proj.name}")


@project_app.command("list")
def project_list(
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Lists all research projects."""
    v_path = get_vault_path(vault)
    svc = ProjectService(v_path)
    projects = svc.list_projects()
    if as_json:
        output_result(projects, as_json=True)
    else:
        table = Table(title="Research Projects")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Status", style="green")
        table.add_column("Research Question")
        for p in projects:
            table.add_row(p.id, p.name, p.status.value, p.research_question or "-")
        console.print(table)


@project_app.command("show")
def project_show(
    project_id: Annotated[str, typer.Argument(help="Project ID (e.g. PRJ-2026-001)")],
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Shows project details and status metrics."""
    v_path = get_vault_path(vault)
    svc = ProjectService(v_path)
    status = svc.get_project_status(project_id)
    if as_json:
        output_result(status, as_json=True)
    else:
        console.print(f"[bold cyan]Project:[/bold cyan] {status['project_id']} - {status['name']}")
        console.print(f"[bold]Status:[/bold] {status['status']}")
        console.print(f"[bold]Experiments:[/bold] {status['experiments_count']}")
        console.print(f"[bold]Runs:[/bold] {status['runs_count']}")
        console.print(f"[bold]Findings:[/bold] {status['findings_count']}")
        console.print(f"[bold]Claims:[/bold] {status['claims_count']}")


# Experiment commands
@experiment_app.command("create")
def experiment_create(
    project_id: Annotated[str, typer.Argument(help="Parent Project ID")],
    title: Annotated[str, typer.Argument(help="Experiment title")],
    hypothesis: Annotated[Optional[str], typer.Option("--hypothesis", "-h", help="Scientific hypothesis")] = None,
    objective: Annotated[Optional[str], typer.Option("--objective", "-o", help="Experiment objective")] = None,
    method: Annotated[Optional[str], typer.Option("--method", "-m", help="Methodology")] = None,
    exploratory: Annotated[bool, typer.Option("--exploratory", help="Mark as exploratory")] = False,
    params: Annotated[Optional[str], typer.Option("--params", "-p", help="Planned parameters as JSON string")] = None,
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Creates a new experiment plan."""
    v_path = get_vault_path(vault)
    svc = ExperimentService(v_path)
    parsed_params = json.loads(params) if params else {}
    exp = svc.create_experiment(
        project_id=project_id,
        title=title,
        hypothesis=hypothesis,
        objective=objective,
        method=method,
        planned_parameters=parsed_params,
        is_exploratory=exploratory,
    )
    if as_json:
        output_result(exp, as_json=True)
    else:
        console.print(f"[bold green]Created experiment {exp.id}:[/bold green] {exp.title} (Status: {exp.status.value})")


@experiment_app.command("list")
def experiment_list(
    project_id: Annotated[Optional[str], typer.Option("--project", "-p")] = None,
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Lists experiments."""
    v_path = get_vault_path(vault)
    svc = ExperimentService(v_path)
    experiments = svc.list_experiments(project_id=project_id)
    if as_json:
        output_result(experiments, as_json=True)
    else:
        table = Table(title="Experiments")
        table.add_column("ID", style="cyan")
        table.add_column("Project", style="magenta")
        table.add_column("Title", style="bold")
        table.add_column("Status", style="yellow")
        table.add_column("Outcome", style="green")
        for e in experiments:
            table.add_row(e.id, e.project_id, e.title, e.status.value, e.outcome.value)
        console.print(table)


@experiment_app.command("pending")
def experiment_pending(
    project_id: Annotated[Optional[str], typer.Option("--project", "-p")] = None,
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Lists all pending/uncompleted experiments."""
    v_path = get_vault_path(vault)
    svc = ExperimentService(v_path)
    experiments = svc.list_pending_experiments(project_id=project_id)
    if as_json:
        output_result(experiments, as_json=True)
    else:
        table = Table(title="Pending Experiments")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="bold")
        table.add_column("Status", style="yellow")
        table.add_column("Outcome", style="green")
        for e in experiments:
            table.add_row(e.id, e.title, e.status.value, e.outcome.value)
        console.print(table)


@experiment_app.command("show")
def experiment_show(
    experiment_id: Annotated[str, typer.Argument(help="Experiment ID")],
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Shows experiment details and markdown content."""
    v_path = get_vault_path(vault)
    svc = ExperimentService(v_path)
    exp, body = svc.get_experiment(experiment_id)
    if as_json:
        output_result(exp, as_json=True)
    else:
        console.print(f"[bold cyan]Experiment {exp.id}:[/bold cyan] {exp.title}")
        console.print(f"[bold]Status:[/bold] {exp.status.value} | [bold]Outcome:[/bold] {exp.outcome.value}")
        console.print(f"[bold]Hypothesis:[/bold] {exp.hypothesis or '-'}")
        console.print(f"[bold]Planned Params:[/bold] {exp.planned_parameters}")
        console.print(f"[bold]Runs:[/bold] {exp.runs}")


@experiment_app.command("validate")
def experiment_validate(
    experiment_id: Annotated[str, typer.Argument(help="Experiment ID")],
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Validates preflight readiness for an experiment."""
    v_path = get_vault_path(vault)
    svc = ExperimentService(v_path)
    res = svc.validate_preflight(experiment_id)
    if as_json:
        output_result(res, as_json=True)
    else:
        console.print(f"[bold green]Experiment {experiment_id} Preflight Check Passed.[/bold green]")


# Run commands
@run_app.command("create")
def run_create(
    experiment_id: Annotated[str, typer.Argument(help="Experiment ID")],
    agent: Annotated[str, typer.Option("--agent", "-a", help="Agent identifier")] = "agent",
    executor: Annotated[str, typer.Option("--executor", "-e", help="local or dsh")] = "local",
    server_id: Annotated[Optional[str], typer.Option("--server-id", "-s", help="Server ID")] = None,
    working_dir: Annotated[Optional[str], typer.Option("--dir", "-d", help="Working directory")] = None,
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Creates a new execution Run linked to an experiment."""
    v_path = get_vault_path(vault)
    svc = RunService(v_path)
    r = svc.create_run(
        experiment_id=experiment_id,
        agent_name=agent,
        executor_type=executor,
        server_id=server_id,
        working_directory=working_dir,
    )
    if as_json:
        output_result(r, as_json=True)
    else:
        console.print(f"[bold green]Created Run {r.id}:[/bold green] for {r.experiment_id} by {r.agent_name}")


@run_app.command("show")
def run_show(
    run_id: Annotated[str, typer.Argument(help="Run ID")],
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Shows run details and execution telemetry."""
    v_path = get_vault_path(vault)
    svc = RunService(v_path)
    r, body = svc.get_run(run_id)
    if as_json:
        output_result(r, as_json=True)
    else:
        console.print(f"[bold cyan]Run {r.id}:[/bold cyan] Status: {r.status.value}")
        console.print(f"[bold]Agent:[/bold] {r.agent_name} | [bold]Executor:[/bold] {r.executor_type}")
        console.print(f"[bold]Actual Params:[/bold] {r.actual_parameters}")
        console.print(f"[bold]Metrics:[/bold] {r.metrics}")
        console.print(f"[bold]Artifacts:[/bold] {r.artifacts}")


@run_app.command("complete")
def run_complete(
    run_id: Annotated[str, typer.Argument(help="Run ID")],
    params: Annotated[str, typer.Option("--actual-params", "-p", help="Actual parameters as JSON string")],
    status: Annotated[str, typer.Option("--status", "-s", help="succeeded/failed/interrupted")] = "succeeded",
    outcome: Annotated[Optional[str], typer.Option("--outcome", "-o", help="positive/negative/inconclusive/failed")] = None,
    metrics: Annotated[Optional[str], typer.Option("--metrics", "-m", help="Metrics JSON")] = None,
    summary: Annotated[Optional[str], typer.Option("--summary", help="Execution summary")] = None,
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Completes an experimental run, records actual parameters and metrics."""
    v_path = get_vault_path(vault)
    svc = RunService(v_path)
    parsed_params = json.loads(params)
    parsed_metrics = json.loads(metrics) if metrics else {}
    status_enum = RunStatus(status)
    outcome_enum = ExperimentOutcome(outcome) if outcome else None

    r = svc.complete_run(
        run_id=run_id,
        status=status_enum,
        actual_parameters=parsed_params,
        metrics=parsed_metrics,
        result_summary=summary,
        experiment_outcome=outcome_enum,
    )
    if as_json:
        output_result(r, as_json=True)
    else:
        console.print(f"[bold green]Completed Run {r.id}:[/bold green] status {r.status.value}")


# Paper commands
@paper_app.command("create")
def paper_create(
    title: Annotated[str, typer.Argument(help="Paper title")],
    citekey: Annotated[str, typer.Option("--citekey", "-c", help="BibTeX citekey")],
    authors: Annotated[Optional[list[str]], typer.Option("--author", "-a", help="Authors")] = None,
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Publication year")] = None,
    doi: Annotated[Optional[str], typer.Option("--doi", help="DOI")] = None,
    abstract: Annotated[Optional[str], typer.Option("--abstract", help="Abstract")] = None,
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Registers a literature paper entry."""
    v_path = get_vault_path(vault)
    svc = PaperService(v_path)
    paper = svc.create_paper(
        title=title,
        citekey=citekey,
        authors=authors or [],
        year=year,
        doi=doi,
        abstract=abstract,
    )
    if as_json:
        output_result(paper, as_json=True)
    else:
        console.print(f"[bold green]Registered paper {paper.id}:[/bold green] {paper.title} ({paper.citekey})")


@paper_app.command("search")
def paper_search(
    query: Annotated[str, typer.Argument(help="Search query")],
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Searches literature notes by keyword, author, or citekey."""
    v_path = get_vault_path(vault)
    svc = PaperService(v_path)
    results = svc.search_papers(query=query)
    if as_json:
        output_result(results, as_json=True)
    else:
        table = Table(title=f"Paper Search: '{query}'")
        table.add_column("ID", style="cyan")
        table.add_column("Citekey", style="magenta")
        table.add_column("Title", style="bold")
        table.add_column("Year")
        table.add_column("Status")
        for p in results:
            table.add_row(p.id, p.citekey, p.title, str(p.year or "-"), p.reading_status.value)
        console.print(table)


# Artifact commands
@artifact_app.command("register")
def artifact_register(
    run_id: Annotated[str, typer.Argument(help="Run ID")],
    file_path: Annotated[str, typer.Argument(help="Artifact file path")],
    role: Annotated[str, typer.Option("--role", "-r", help="raw_data, checkpoint, metrics, figure, etc.")] = "metrics",
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="Artifact custom name")] = None,
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Registers an artifact file and computes cryptographic SHA-256."""
    v_path = get_vault_path(vault)
    svc = ArtifactService(v_path)
    art = svc.register_artifact(run_id=run_id, path=file_path, role=role, name=name)
    if as_json:
        output_result(art, as_json=True)
    else:
        console.print(f"[bold green]Registered artifact {art.id}:[/bold green] {art.name} (SHA-256: {art.sha256[:12]}...)")


# Context command
@context_app.command("build")
def context_build(
    target_id: Annotated[str, typer.Argument(help="Experiment ID or Project ID")],
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
) -> None:
    """Builds a comprehensive Research Context Pack Markdown document."""
    v_path = get_vault_path(vault)
    svc = ContextService(v_path)
    pack_md = svc.build_context(target_id)
    console.print(pack_md)


# Handoff command
@handoff_app.command("update")
def handoff_update(
    project_id: Annotated[str, typer.Argument(help="Project ID")],
    focus: Annotated[str, typer.Option("--focus", "-f", help="Current active focus")],
    completed: Annotated[Optional[list[str]], typer.Option("--completed", "-c", help="Completed items")] = None,
    next_steps: Annotated[Optional[list[str]], typer.Option("--next", "-n", help="Next steps")] = None,
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
) -> None:
    """Updates HANDOFF.md and STATUS.md for the project."""
    v_path = get_vault_path(vault)
    svc = HandoffService(v_path)
    res = svc.update_handoff(
        project_id=project_id,
        current_focus=focus,
        completed_since_last=completed,
        next_steps=next_steps,
    )
    console.print(f"[bold green]Handoff updated for {project_id}.[/bold green]")


# Top-level audit
@app.command("audit")
def audit(
    project_id: Annotated[Optional[str], typer.Option("--project", "-p", help="Project ID")] = None,
    vault: Annotated[Optional[str], typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Performs full referential integrity and evidence audit on the vault."""
    v_path = get_vault_path(vault)
    svc = AuditService(v_path)
    res = svc.run_audit(project_id=project_id)
    if as_json:
        output_result(res, as_json=True)
    else:
        status_color = "green" if res["status"] == "passed" else "red"
        console.print(f"[{status_color}]Audit Result: {res['status'].upper()}[/{status_color}] (Errors: {res['errors']}, Warnings: {res['warnings']})")
        console.print(f"Report: {res['report_path']}")
        if res["issues"]:
            for issue in res["issues"]:
                console.print(f"- [{issue['level']}] {issue['entity']}: {issue['message']}")
    if res["errors"] > 0:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
