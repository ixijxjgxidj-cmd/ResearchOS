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
from researchos.core.paper_service import PaperService
from researchos.core.project_memory_service import ProjectMemoryService
from researchos.core.project_service import ProjectService
from researchos.core.retrieval_service import RetrievalService

app = typer.Typer(
    name="researchos",
    help="ResearchOS: Universal Long-Term Research Memory System (Markdown-First, Project-Isolated)",
)
console = Console()
err_console = Console(stderr=True)

project_app = typer.Typer(name="project", help="Manage independent project folders and status")
project_memory_app = typer.Typer(name="memory", help="Always-on Project Memory (MEMORY.md) commands")
memory_app = typer.Typer(name="memory", help="Create, search, update, supersede, and archive memories")
context_app = typer.Typer(name="context", help="Build token-budgeted agent context packs")
handoff_app = typer.Typer(name="handoff", help="Record and retrieve agent shift handoffs")
paper_app = typer.Typer(name="paper", help="Paper Writing Mode: experiment inventory and evidence coverage")
hook_app = typer.Typer(name="hook", help="Memory Hook Core: context compaction recovery and session orientation")

project_app.add_typer(project_memory_app)
app.add_typer(project_app)
app.add_typer(memory_app)
app.add_typer(context_app)
app.add_typer(handoff_app)
app.add_typer(paper_app)
app.add_typer(hook_app)


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
    strict: Annotated[bool, typer.Option("--strict/--no-strict", help="Fail validation on broken links or invalid relations")] = True,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Validates schemas, links, relations, and folder integrity across all project memories."""
    v_path = get_vault_path(vault)
    svc = ProjectService(v_path)
    res = svc.validate_project(project_id, strict=strict)
    if as_json:
        output_data(res, as_json=True)
    else:
        status_color = "green" if res["valid"] else "red"
        console.print(f"[{status_color}]Project Validation: {'PASSED' if res['valid'] else 'FAILED'}[/{status_color}]")
        console.print(f"  Total Valid Memories: {res['total_memories']}")
        console.print(f"  Checked Files:        {res['checked_files']}")
        if res["errors"]:
            console.print("[bold red]Errors:[/bold red]")
            for err in res["errors"]:
                console.print(f"  - {err}")
        if res["broken_links"]:
            console.print(f"[bold yellow]Broken Links ({len(res['broken_links'])}):[/bold yellow]")
            for bl in res["broken_links"]:
                console.print(f"  - {bl['message']}")
        if res["invalid_relations"]:
            console.print(f"[bold yellow]Invalid Relations ({len(res['invalid_relations'])}):[/bold yellow]")
            for ir in res["invalid_relations"]:
                console.print(f"  - {ir['message']}")
        if res["orphan_memories"]:
            console.print(f"[bold yellow]Orphan Memories ({len(res['orphan_memories'])}):[/bold yellow]")
            for om in res["orphan_memories"]:
                console.print(f"  - {om}")


# =========================================================================
# Project Memory (MEMORY.md) CLI Commands
# =========================================================================

@project_memory_app.command("get")
def project_memory_get_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Reads the compressed Always-on Project Memory (MEMORY.md)."""
    v_path = get_vault_path(vault)
    pms = ProjectMemoryService(v_path)
    content = pms.get_project_memory(project_id)
    if as_json:
        output_data({"project_id": project_id, "memory_content": content}, as_json=True)
    else:
        console.print(content)


@project_memory_app.command("update")
def project_memory_update_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    content: Annotated[str, typer.Option("--content", "-c", help="New Markdown text for MEMORY.md")],
    reason: Annotated[str | None, typer.Option("--reason", "-r", help="Update reason")] = None,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Atomically updates MEMORY.md."""
    v_path = get_vault_path(vault)
    pms = ProjectMemoryService(v_path)
    updated = pms.update_project_memory(project_id, content=content, reason=reason)
    if as_json:
        output_data({"project_id": project_id, "status": "success", "content": updated}, as_json=True)
    else:
        console.print(f"[bold green]Updated MEMORY.md for project:[/bold green] `{project_id}`")


@project_memory_app.command("validate")
def project_memory_validate_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Validates MEMORY.md against the 10 canonical sections, cited IDs, and token budget."""
    v_path = get_vault_path(vault)
    pms = ProjectMemoryService(v_path)
    res = pms.validate_project_memory(project_id)
    output_data(res, as_json=as_json)


@project_memory_app.command("rebuild")
def project_memory_rebuild_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    tokens: Annotated[int, typer.Option("--tokens", "-t", help="Target token budget")] = 2000,
    clean: Annotated[bool, typer.Option("--clean", help="Discard custom notes and rebuild clean template")] = False,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Reconstructs MEMORY.md using PROJECT.md, STATE.md, and key memories, preserving custom notes by default."""
    v_path = get_vault_path(vault)
    pms = ProjectMemoryService(v_path)
    res = pms.rebuild_project_memory(
        project_id, max_tokens=tokens, preserve_custom_notes=not clean
    )
    if as_json:
        output_data({"project_id": project_id, "status": "success", "content": res}, as_json=True)
    else:
        console.print(f"[bold green]Rebuilt MEMORY.md for project:[/bold green] `{project_id}`")
        console.print(res)


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
    source_type: Annotated[str | None, typer.Option("--source-type", help="Source type (agent, human, experiment, imported, system)")] = None,
    agent: Annotated[str | None, typer.Option("--agent", "-a", help="Source agent ID")] = None,
    skill: Annotated[str | None, typer.Option("--skill", "-s", help="Source skill")] = None,
    source_ref: Annotated[str | None, typer.Option("--ref", "-r", help="Source reference (URL, run, commit)")] = None,
    confidence: Annotated[float | None, typer.Option("--confidence", help="Confidence score (0.0 to 1.0)")] = None,
    experiment_id: Annotated[str | None, typer.Option("--experiment-id", help="Experiment run identifier")] = None,
    paper_section: Annotated[str | None, typer.Option("--section", help="Paper outline section, e.g. '4.1 Main Results'")] = None,
    metrics_summary: Annotated[str | None, typer.Option("--metrics", help="Summary of quantitative metrics")] = None,
    parent_experiment: Annotated[str | None, typer.Option("--parent", help="Parent experiment ID")] = None,
    artifact_paths: Annotated[list[str] | None, typer.Option("--artifact", help="Artifact file path")] = None,
    standard_prefix: Annotated[bool, typer.Option("--standard-prefix", help="Use standard DEC-001/OBS-001 prefix ID")] = False,
    slug: Annotated[bool, typer.Option("--slug", help="Append slugified title to filename")] = False,
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
        source_type=source_type,
        source_agent=agent,
        source_skill=skill,
        source_ref=source_ref,
        confidence=confidence,
        experiment_id=experiment_id,
        paper_section=paper_section,
        metrics_summary=metrics_summary,
        parent_experiment=parent_experiment,
        artifact_paths=artifact_paths,
        use_standard_prefix=standard_prefix,
        use_slug=slug,
    )
    if as_json:
        output_data(mem.model_dump(mode="json"), as_json=True)
    else:
        console.print(f"[bold green]Memory recorded:[/bold green] `{mem.id}`")
        console.print(f"  [cyan]Title:[/cyan]       {mem.title}")
        console.print(f"  [cyan]Type:[/cyan]        {mem.type.value}")
        console.print(f"  [cyan]Source Type:[/cyan] {mem.source_type}")
        console.print(f"  [cyan]File:[/cyan]        {mem.file_path}")


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
        stat_val = mem.status.value if hasattr(mem.status, "value") else str(mem.status)
        console.print(f"[bold]Status:[/bold] {stat_val}")
        console.print(f"[bold]Tags:[/bold] {mem.tags}")
        console.print("\n" + mem.content)


@memory_app.command("search")
def memory_search_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier (use '*' for cross-project)")],
    query: Annotated[str | None, typer.Option("--query", "-q", help="Search query keywords")] = None,
    type: Annotated[str | None, typer.Option("--type", "-T", help="Filter by memory type")] = None,
    tags: Annotated[list[str] | None, typer.Option("--tag", "-t", help="Filter by tags")] = None,
    tag_mode: Annotated[str, typer.Option("--tag-mode", help="Tag match mode (OR / AND)")] = "OR",
    status: Annotated[str | None, typer.Option("--status", "-s", help="Filter by status (active, superseded, archived)")] = None,
    source_agent: Annotated[str | None, typer.Option("--agent", "-a", help="Filter by source agent")] = None,
    source_skill: Annotated[str | None, typer.Option("--skill", help="Filter by source skill")] = None,
    source_type: Annotated[str | None, typer.Option("--source-type", help="Filter by source type")] = None,
    min_confidence: Annotated[float | None, typer.Option("--min-confidence", help="Minimum confidence threshold")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max search hits")] = 20,
    cross_project: Annotated[bool, typer.Option("--cross-project", help="Search across all projects")] = False,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Searches memories within a project with BM25 ranking and multi-field filters."""
    v_path = get_vault_path(vault)
    svc = RetrievalService(v_path)
    hits = svc.search_memories(
        project_id=project_id,
        query=query,
        type=type,
        tags=tags,
        tag_mode="AND" if tag_mode.upper() == "AND" else "OR",
        status=status,
        source_agent=source_agent,
        source_skill=source_skill,
        source_type=source_type,
        min_confidence=min_confidence,
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
        table.add_column("Score", style="green")
        table.add_column("Path", style="dim")
        table.add_column("Snippet")
        for h in hits:
            table.add_row(h.memory_id, h.type, h.title, f"{h.score:.2f}", h.file_path, h.snippet)
        console.print(table)


@memory_app.command("related")
def memory_related_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    memory_id: Annotated[str, typer.Argument(help="Memory identifier")],
    depth: Annotated[int, typer.Option("--depth", "-d", help="Max relation traversal depth (1-3)")] = 1,
    direction: Annotated[str, typer.Option("--direction", help="Direction: outbound, inbound, both")] = "both",
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Traverses the memory relation graph (related, supersedes, superseded_by)."""
    v_path = get_vault_path(vault)
    svc = RetrievalService(v_path)
    hits = svc.search_related_graph(
        project_id=project_id,
        memory_id=memory_id,
        max_depth=depth,
        direction=direction if direction in ("outbound", "inbound", "both") else "both",
    )
    if as_json:
        output_data([h.model_dump() for h in hits], as_json=True)
    else:
        table = Table(title=f"Related Memories for {memory_id} (Total: {len(hits)})")
        table.add_column("Memory ID", style="cyan")
        table.add_column("Relation", style="magenta")
        table.add_column("Depth", style="yellow")
        table.add_column("Direction", style="dim")
        table.add_column("Title", style="bold")
        for h in hits:
            table.add_row(h.memory_id, h.relation_type, str(h.depth), h.direction, h.title)
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
    mode: Annotated[str, typer.Option("--mode", "-m", help="Context mode: quick, task, paper, full")] = "quick",
    max_tokens: Annotated[int, typer.Option("--max-tokens", "-b", help="Max tokens budget")] = 4000,
    history: Annotated[bool, typer.Option("--history/--no-history", help="Include historical / superseded records in full mode")] = False,
    section: Annotated[str | None, typer.Option("--section", "-s", help="Paper outline section for paper mode")] = None,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Builds a prioritized, token-budgeted agent context pack."""
    v_path = get_vault_path(vault)
    builder = ContextBuilder(v_path)
    pack, meta = builder.build_context_pack(
        project_id=project_id,
        task=task,
        context_mode=mode,
        max_tokens=max_tokens,
        include_history=history,
        paper_section=section,
    )
    if as_json:
        output_data({"context_pack": pack, "metadata": meta.model_dump()}, as_json=True)
    else:
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


# =========================================================================
# Paper Writing Mode CLI Commands
# =========================================================================

@paper_app.command("inventory")
def paper_inventory_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    section: Annotated[str | None, typer.Option("--section", "-s", help="Filter by paper section")] = None,
    status: Annotated[list[str] | None, typer.Option("--status", help="Filter by status (completed, failed, interrupted, etc.)")] = None,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Retrieves lightweight experiment metadata for paper writing (Phase A/B)."""
    v_path = get_vault_path(vault)
    ps = PaperService(v_path)
    items = ps.get_paper_inventory(project_id, paper_section=section, status_filter=status)
    if as_json:
        output_data([i.model_dump() for i in items], as_json=True)
    else:
        table = Table(title=f"Paper Experiment Inventory: {project_id} (Total: {len(items)})")
        table.add_column("Memory ID", style="cyan")
        table.add_column("Exp ID", style="magenta")
        table.add_column("Status", style="yellow")
        table.add_column("Section", style="dim")
        table.add_column("Title", style="bold")
        table.add_column("Metrics", style="green")
        for it in items:
            table.add_row(
                it.memory_id,
                it.experiment_id or "-",
                it.status,
                it.paper_section or "-",
                it.title,
                it.metrics_summary or "-",
            )
        console.print(table)


@paper_app.command("coverage")
def paper_coverage_cmd(
    project_id: Annotated[str, typer.Argument(help="Project identifier")],
    section: Annotated[str, typer.Option("--section", "-s", help="Paper section name")],
    loaded: Annotated[list[str] | None, typer.Option("--loaded", "-l", help="Loaded memory ID")] = None,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Checks Evidence Coverage for a paper section (Phase D)."""
    v_path = get_vault_path(vault)
    ps = PaperService(v_path)
    cov = ps.check_evidence_coverage(
        project_id=project_id,
        paper_section=section,
        loaded_memory_ids=loaded or [],
    )
    if as_json:
        output_data(cov.model_dump(), as_json=True)
    else:
        status_color = "green" if cov.is_fully_covered else "yellow"
        console.print(f"[{status_color}]Evidence Coverage: {'COMPLETE' if cov.is_fully_covered else 'INCOMPLETE'}[/{status_color}]")
        console.print(f"  Target Evidence Count: {len(cov.target_memory_ids)}")
        console.print(f"  Loaded Evidence Count: {len(cov.loaded_memory_ids)}")
        console.print(f"  Pending Evidence Count: {len(cov.pending_memory_ids)}")
        if cov.pending_memory_ids:
            console.print("[bold yellow]Pending Evidence (Must inspect before drafting):[/bold yellow]")
            for pe in cov.missing_evidence:
                console.print(f"  - {pe}")
        if cov.missing_artifacts:
            console.print("[bold red]Missing Artifact Files on Disk:[/bold red]")
            for ma in cov.missing_artifacts:
                console.print(f"  - {ma}")


# =========================================================================
# Hook CLI Commands
# =========================================================================

@hook_app.command("run")
def hook_run_cmd(
    event: Annotated[str, typer.Option("--event", "-e", help="Lifecycle event: session_start, pre_compaction, post_compaction, session_end")],
    project: Annotated[str | None, typer.Option("--project", "-p", help="Target project_id (auto-resolved if omitted)")] = None,
    agent: Annotated[str | None, typer.Option("--agent", "-a", help="Agent identifier")] = None,
    task: Annotated[str | None, typer.Option("--task", "-t", help="Current task focus")] = None,
    work: Annotated[list[str] | None, typer.Option("--work", "-w", help="Completed work item")] = None,
    next_steps: Annotated[list[str] | None, typer.Option("--next", "-n", help="Next action item")] = None,
    blockers: Annotated[list[str] | None, typer.Option("--blocker", "-b", help="Current blocker item")] = None,
    event_id: Annotated[str | None, typer.Option("--event-id", help="Explicit event identifier for idempotency")] = None,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Executes a Memory Hook Core lifecycle event."""
    from researchos.hooks.adapters.generic_cli import GenericCLIAdapter
    v_path = get_vault_path(vault)
    adapter = GenericCLIAdapter(v_path)
    ev = event.lower().strip()

    if ev in ("session_start", "start"):
        out = adapter.handle_session_start(project_id=project, agent_id=agent, event_id=event_id, as_json=as_json)
    elif ev in ("pre_compaction", "pre-compact"):
        out = adapter.handle_pre_compaction(
            project_id=project,
            agent_id=agent,
            task=task,
            completed_work=work,
            next_steps=next_steps,
            blockers=blockers,
            event_id=event_id,
            as_json=as_json,
        )
    elif ev in ("post_compaction", "post-compact", "compact"):
        out = adapter.handle_post_compaction(project_id=project, agent_id=agent, event_id=event_id, as_json=as_json)
    elif ev in ("session_end", "end"):
        out = adapter.handle_session_end(
            project_id=project,
            agent_id=agent,
            task=task,
            completed_work=work,
            next_steps=next_steps,
            event_id=event_id,
            as_json=as_json,
        )
    else:
        err_console.print(f"[bold red]Unknown event:[/bold red] {event}")
        raise typer.Exit(1)

    console.print(out)


@hook_app.command("session-start")
def hook_session_start_cmd(
    project: Annotated[str | None, typer.Option("--project", "-p")] = None,
    agent: Annotated[str | None, typer.Option("--agent", "-a")] = None,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Dispatches Event A: Session Start hook."""
    from researchos.hooks.adapters.generic_cli import GenericCLIAdapter
    v_path = get_vault_path(vault)
    adapter = GenericCLIAdapter(v_path)
    console.print(adapter.handle_session_start(project_id=project, agent_id=agent, as_json=as_json))


@hook_app.command("pre-compaction")
def hook_pre_compaction_cmd(
    project: Annotated[str | None, typer.Option("--project", "-p")] = None,
    agent: Annotated[str | None, typer.Option("--agent", "-a")] = None,
    task: Annotated[str | None, typer.Option("--task", "-t")] = None,
    work: Annotated[list[str] | None, typer.Option("--work", "-w")] = None,
    next_steps: Annotated[list[str] | None, typer.Option("--next", "-n")] = None,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Dispatches Event B: Before Compaction hook."""
    from researchos.hooks.adapters.generic_cli import GenericCLIAdapter
    v_path = get_vault_path(vault)
    adapter = GenericCLIAdapter(v_path)
    console.print(adapter.handle_pre_compaction(project_id=project, agent_id=agent, task=task, completed_work=work, next_steps=next_steps, as_json=as_json))


@hook_app.command("post-compaction")
def hook_post_compaction_cmd(
    project: Annotated[str | None, typer.Option("--project", "-p")] = None,
    agent: Annotated[str | None, typer.Option("--agent", "-a")] = None,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Dispatches Event C: After Compaction (CORE) hook."""
    from researchos.hooks.adapters.generic_cli import GenericCLIAdapter
    v_path = get_vault_path(vault)
    adapter = GenericCLIAdapter(v_path)
    console.print(adapter.handle_post_compaction(project_id=project, agent_id=agent, as_json=as_json))


# =========================================================================
# Migration CLI Command
# =========================================================================

@app.command("migrate")
def migrate_cmd(
    project: Annotated[str | None, typer.Option("--project", "-p", help="Target specific project_id")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Simulate migration without modifying files")] = False,
    backup: Annotated[bool, typer.Option("--backup/--no-backup", help="Create backup before migration")] = True,
    vault: Annotated[str | None, typer.Option("--vault", "-v")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Losslessly migrates projects to the v3 Lightweight Scientific Memory architecture."""
    from scripts.migrate_v2_to_v3 import run_migration_v2_to_v3
    v_path = get_vault_path(vault)
    res = run_migration_v2_to_v3(vault_root=v_path, target_project_id=project, dry_run=dry_run, backup=backup)
    output_data(res, as_json=as_json)


if __name__ == "__main__":
    app()
