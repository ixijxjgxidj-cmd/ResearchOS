"""Official Command Line Interface (CLI) for ResearchOS Universal Memory."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from researchos.config.settings import Settings
from researchos.core.context_builder import ContextBuilder
from researchos.core.handoff_service import HandoffService
from researchos.core.memory_service import MemoryService
from researchos.core.project_service import ProjectService
from researchos.core.retrieval_service import RetrievalService

app = typer.Typer(
    name="researchos",
    help="ResearchOS: Universal Long-Term Research Memory System (Markdown-First, Project-Isolated)",
)
console = Console()
err_console = Console(stderr=True)

project_app = typer.Typer(name="project", help="Manage independent project folders and status")
memory_app = typer.Typer(name="memory", help="Create, search, update, supersede, and archive memories")
context_app = typer.Typer(name="context", help="Build token-budgeted agent context packs")
handoff_app = typer.Typer(name="handoff", help="Record and retrieve agent shift handoffs")

app.add_typer(project_app)
app.add_typer(memory_app)
app.add_typer(context_app)
app.add_typer(handoff_app)


def get_vault_path(vault: str | None) -> Path:
    return Settings.discover_vault_root(vault)


def output_data(data: Any, as_json: bool = False) -> None:
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


# =========================================================================
# Project CLI Commands
# =========================================================================

@project_app.command("create")
def project_create_cmd(
    name: Annotated[str, typer.Argument(help="Human-readable project title")],
    id: Annotated[str | None, typer.Option("--id", help="Explicit project directory ID")] = None,
    description: Annotated[str | None, typer.Option("--desc", "-d", help="Short project description")] = None,
    goal: Annotated[str | None, typer.Option("--goal", "-g", help="Primary research objective")] = None,
    tags: Annotated[list[str] | None, typer.Option("--tag", "-t", help="Project tags")] = None,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Idempotently creates a new independent project folder with standard structure."""
    v_path = get_vault_path(vault)
    svc = ProjectService(v_path)
    proj = svc.create_project(
        name=name,
        project_id=id,
        description=description,
        research_goal=goal,
        tags=tags,
    )
    if as_json:
        output_data(proj.model_dump(mode="json"), as_json=True)
    else:
        console.print(f"[bold green]Project initialized:[/bold green] {proj.project_name}")
        console.print(f"  [cyan]Project ID:[/cyan]   {proj.project_id}")
        console.print(f"  [cyan]Directory:[/cyan]    {proj.project_dir}")


@project_app.command("list")
def project_list_cmd(
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Lists all research projects in the vault."""
    v_path = get_vault_path(vault)
    svc = ProjectService(v_path)
    projects = svc.list_projects()
    if as_json:
        output_data([p.model_dump(mode="json") for p in projects], as_json=True)
    else:
        table = Table(title="Research Projects")
        table.add_column("Project ID", style="cyan")
        table.add_column("Project Name", style="bold")
        table.add_column("Status", style="green")
        table.add_column("Updated At")
        for p in projects:
            table.add_row(p.project_id, p.project_name, p.status, p.updated_at.strftime("%Y-%m-%d %H:%M"))
        console.print(table)


@project_app.command("get")
def project_get_cmd(
    project_id: Annotated[str, typer.Argument(help="Project directory identifier")],
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Displays project details, state, and file path."""
    v_path = get_vault_path(vault)
    svc = ProjectService(v_path)
    proj = svc.get_project(project_id)
    if as_json:
        output_data(proj.model_dump(mode="json"), as_json=True)
    else:
        console.print(f"[bold green]Project:[/bold green] {proj.project_name} (`{proj.project_id}`)")
        console.print(f"[bold]Goal:[/bold] {proj.frontmatter.research_goal}")
        console.print(f"[bold]Status:[/bold] {proj.status}")
        console.print(f"[bold]Updated:[/bold] {proj.updated_at.isoformat()}")


@project_app.command("rebuild-index")
def project_rebuild_index_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Scans all memory files and fully regenerates INDEX.md."""
    v_path = get_vault_path(vault)
    svc = ProjectService(v_path)
    res = svc.rebuild_index(project_id)
    output_data(res, as_json=as_json)


@project_app.command("validate")
def project_validate_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Validates schemas and links across all project memories."""
    v_path = get_vault_path(vault)
    svc = ProjectService(v_path)
    res = svc.validate_project(project_id)
    output_data(res, as_json=as_json)


# =========================================================================
# Memory CLI Commands
# =========================================================================

@memory_app.command("add")
def memory_add_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    type: Annotated[str, typer.Option("--type", "-T", help="Memory type (knowledge, decision, hypothesis, observation, negative, reference, handoff)")],
    title: Annotated[str, typer.Option("--title", "-t", help="Memory title")],
    content: Annotated[str, typer.Option("--content", "-c", help="Markdown content body")],
    tags: Annotated[list[str] | None, typer.Option("--tag", help="Tags")] = None,
    agent: Annotated[str | None, typer.Option("--agent", "-a", help="Source agent ID")] = None,
    skill: Annotated[str | None, typer.Option("--skill", "-s", help="Source skill")] = None,
    source_ref: Annotated[str | None, typer.Option("--ref", "-r", help="Source reference (URL, run, commit)")] = None,
    confidence: Annotated[float | None, typer.Option("--confidence", help="Confidence score (0.0 to 1.0)")] = None,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Atomically records a new universal memory."""
    v_path = get_vault_path(vault)
    svc = MemoryService(v_path)
    mem = svc.add_memory(
        project_id=project_id,
        type=type,
        title=title,
        content=content,
        tags=tags,
        source_agent=agent,
        source_skill=skill,
        source_ref=source_ref,
        confidence=confidence,
    )
    if as_json:
        output_data(mem.model_dump(mode="json"), as_json=True)
    else:
        console.print(f"[bold green]Memory recorded:[/bold green] `{mem.id}`")
        console.print(f"  [cyan]Title:[/cyan]     {mem.title}")
        console.print(f"  [cyan]Type:[/cyan]      {mem.type.value}")
        console.print(f"  [cyan]File:[/cyan]      {mem.file_path}")


@memory_app.command("get")
def memory_get_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    memory_id: Annotated[str, typer.Argument(help="Memory identifier (MEM-YYYY-NNNN)")],
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Reads a memory record by ID."""
    v_path = get_vault_path(vault)
    svc = MemoryService(v_path)
    mem = svc.get_memory(project_id, memory_id)
    if as_json:
        output_data(mem.model_dump(mode="json"), as_json=True)
    else:
        console.print(f"[bold green]Memory:[/bold green] {mem.id} - {mem.title} ({mem.type.value})")
        console.print(f"[bold]Status:[/bold] {mem.status.value}")
        console.print(f"[bold]Tags:[/bold] {mem.tags}")
        console.print("\n" + mem.content)


@memory_app.command("search")
def memory_search_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier (use '*' for cross-project)")],
    query: Annotated[str | None, typer.Option("--query", "-q", help="Search query keywords")] = None,
    type: Annotated[str | None, typer.Option("--type", "-T", help="Filter by memory type")] = None,
    tags: Annotated[list[str] | None, typer.Option("--tag", "-t", help="Filter by tags")] = None,
    status: Annotated[str | None, typer.Option("--status", "-s", help="Filter by status (active, superseded, archived)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max search hits")] = 20,
    cross_project: Annotated[bool, typer.Option("--cross-project", help="Search across all projects")] = False,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Searches memories within a project (or across projects)."""
    v_path = get_vault_path(vault)
    svc = RetrievalService(v_path)
    hits = svc.search_memories(
        project_id=project_id,
        query=query,
        type=type,
        tags=tags,
        status=status,
        limit=limit,
        cross_project=cross_project,
    )
    if as_json:
        output_data([h.model_dump() for h in hits], as_json=True)
    else:
        table = Table(title=f"Search Results (Total: {len(hits)})")
        table.add_column("Memory ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Title", style="bold")
        table.add_column("Path", style="dim")
        table.add_column("Snippet")
        for h in hits:
            table.add_row(h.memory_id, h.type, h.title, h.file_path, h.snippet)
        console.print(table)


@memory_app.command("update")
def memory_update_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    memory_id: Annotated[str, typer.Argument(help="Memory identifier")],
    title: Annotated[str | None, typer.Option("--title", "-t", help="New title")] = None,
    content: Annotated[str | None, typer.Option("--content", "-c", help="New markdown content")] = None,
    confidence: Annotated[float | None, typer.Option("--confidence", help="Confidence score")] = None,
    status: Annotated[str | None, typer.Option("--status", help="New status")] = None,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Safely updates a memory record in place."""
    v_path = get_vault_path(vault)
    svc = MemoryService(v_path)
    mem = svc.update_memory(
        project_id=project_id,
        memory_id=memory_id,
        title=title,
        content=content,
        confidence=confidence,
        status=status,
    )
    output_data(mem.model_dump(mode="json"), as_json=as_json)


@memory_app.command("supersede")
def memory_supersede_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    old_memory_id: Annotated[str, typer.Argument(help="Old memory identifier to supersede")],
    title: Annotated[str, typer.Option("--title", "-t", help="Title of new memory")],
    content: Annotated[str, typer.Option("--content", "-c", help="Content of new memory")],
    reason: Annotated[str, typer.Option("--reason", "-r", help="Explanation for revising / superseding the old memory")],
    type: Annotated[str | None, typer.Option("--type", "-T", help="Type of new memory")] = None,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Supersedes an old memory with a revised memory, recording the reason."""
    v_path = get_vault_path(vault)
    svc = MemoryService(v_path)
    new_mem = svc.supersede_memory(
        project_id=project_id,
        old_memory_id=old_memory_id,
        title=title,
        content=content,
        reason=reason,
        type=type,
    )
    if as_json:
        output_data(new_mem.model_dump(mode="json"), as_json=True)
    else:
        console.print("[bold green]Memory superseded successfully:[/bold green]")
        console.print(f"  [cyan]Old Memory:[/cyan] {old_memory_id} (marked superseded)")
        console.print(f"  [cyan]New Memory:[/cyan] {new_mem.id} ({new_mem.file_path})")


@memory_app.command("archive")
def memory_archive_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    memory_id: Annotated[str, typer.Argument(help="Memory identifier to archive")],
    reason: Annotated[str | None, typer.Option("--reason", "-r", help="Archival reason")] = None,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Moves a memory to archive/ and updates status."""
    v_path = get_vault_path(vault)
    svc = MemoryService(v_path)
    mem = svc.archive_memory(project_id, memory_id, reason=reason)
    output_data(mem.model_dump(mode="json"), as_json=as_json)


# =========================================================================
# Context Builder CLI Commands
# =========================================================================

@context_app.command("build")
def context_build_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    task: Annotated[str | None, typer.Option("--task", "-t", help="Specific task focus")] = None,
    mode: Annotated[str, typer.Option("--mode", "-m", help="Context mode: quick, task, full")] = "quick",
    max_tokens: Annotated[int, typer.Option("--max-tokens", "-b", help="Max tokens budget")] = 4000,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
) -> None:
    """Builds a prioritized, token-budgeted agent context pack."""
    v_path = get_vault_path(vault)
    builder = ContextBuilder(v_path)
    pack = builder.build_context(
        project_id=project_id,
        task=task,
        context_mode=mode,
        max_tokens=max_tokens,
    )
    console.print(pack)


# =========================================================================
# Handoff CLI Commands
# =========================================================================

@handoff_app.command("create")
def handoff_create_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    task: Annotated[str, typer.Option("--task", "-t", help="Current task description")],
    completed: Annotated[list[str] | None, typer.Option("--completed", "-c", help="Completed work item")] = None,
    progress: Annotated[str | None, typer.Option("--progress", "-p", help="Current progress summary")] = None,
    finding: Annotated[list[str] | None, typer.Option("--finding", "-f", help="Key finding")] = None,
    decision: Annotated[list[str] | None, typer.Option("--decision", "-d", help="Decision made")] = None,
    issue: Annotated[list[str] | None, typer.Option("--issue", "-i", help="Issue or blocker")] = None,
    unresolved: Annotated[list[str] | None, typer.Option("--unresolved", "-u", help="Unresolved item")] = None,
    next_step: Annotated[list[str] | None, typer.Option("--next", "-n", help="Next step for incoming agent")] = None,
    related_memories: Annotated[list[str] | None, typer.Option("--mem", help="Related memory ID")] = None,
    related_files: Annotated[list[str] | None, typer.Option("--file", help="Related file path")] = None,
    agent: Annotated[str | None, typer.Option("--agent", "-a", help="Executing agent ID")] = None,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Records an agent shift handoff and synchronizes STATE.md."""
    v_path = get_vault_path(vault)
    svc = HandoffService(v_path)
    mem = svc.create_handoff(
        project_id=project_id,
        task=task,
        completed_work=completed,
        current_progress=progress,
        important_findings=finding,
        decisions_made=decision,
        issues_encountered=issue,
        unresolved_items=unresolved,
        next_steps=next_step,
        related_memory_ids=related_memories,
        related_files=related_files,
        agent_id=agent,
    )
    if as_json:
        output_data(mem.model_dump(mode="json"), as_json=True)
    else:
        console.print(f"[bold green]Handoff recorded successfully:[/bold green] `{mem.id}`")
        console.print("  Updated [cyan]HANDOFF.md[/cyan] and [cyan]STATE.md[/cyan]")


@handoff_app.command("get")
def handoff_get_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
) -> None:
    """Displays the latest HANDOFF.md content."""
    v_path = get_vault_path(vault)
    svc = HandoffService(v_path)
    text = svc.get_latest_handoff(project_id)
    console.print(text)


if __name__ == "__main__":
    app()
