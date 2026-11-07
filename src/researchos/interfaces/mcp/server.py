"""Official Model Context Protocol (MCP) server for ResearchOS Universal Memory."""

import argparse
from typing import Any

from mcp.server.mcpserver import MCPServer

from researchos.config.settings import Settings
from researchos.core.context_builder import ContextBuilder
from researchos.core.handoff_service import HandoffService
from researchos.core.memory_service import MemoryService
from researchos.core.project_service import ProjectService
from researchos.core.retrieval_service import RetrievalService
from researchos.utils.exceptions import ResearchOSError

mcp = MCPServer(
    name="researchos",
    description="Agent-independent, Project-isolated Universal Long-Term Research Memory System.",
)


@mcp.custom_route("/", methods=["GET"])
async def root_endpoint(request: Any) -> Any:
    from starlette.responses import JSONResponse
    return JSONResponse({
        "status": "healthy",
        "service": "ResearchOS Universal Memory MCP Server",
        "version": "2.0.0",
        "endpoints": {
            "sse": "/sse",
            "messages": "/messages/",
            "health": "/health",
        },
    })


@mcp.custom_route("/health", methods=["GET"])
async def health_endpoint(request: Any) -> Any:
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok"})


def get_core_services(vault_root: str | None = None) -> tuple[
    ProjectService,
    MemoryService,
    RetrievalService,
    ContextBuilder,
    HandoffService,
]:
    root = Settings.discover_vault_root(vault_root)
    p_svc = ProjectService(root)
    m_svc = MemoryService(root)
    r_svc = RetrievalService(root)
    c_bld = ContextBuilder(root)
    h_svc = HandoffService(root)
    return p_svc, m_svc, r_svc, c_bld, h_svc


# =========================================================================
# 1. Project Management Tools
# =========================================================================

@mcp.tool(description="Idempotently creates a new independent research project folder with standard structure.")
def project_create(
    name: str,
    project_id: str | None = None,
    description: str | None = None,
    research_goal: str | None = None,
    tags: list[str] | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        p_svc = get_core_services(vault_root)[0]
        proj = p_svc.create_project(
            name=name,
            project_id=project_id,
            description=description,
            research_goal=research_goal,
            tags=tags,
        )
        return {
            "status": "success",
            "project_id": proj.project_id,
            "project_name": proj.project_name,
            "project_dir": proj.project_dir,
            "updated_at": proj.updated_at.isoformat(),
        }
    except ResearchOSError as exc:
        return {"status": "error", "message": exc.message, "details": exc.details}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@mcp.tool(description="Lists all independent research projects in the ResearchVault.")
def project_list(vault_root: str | None = None) -> dict[str, Any]:
    try:
        p_svc = get_core_services(vault_root)[0]
        projects = p_svc.list_projects()
        return {
            "status": "success",
            "total": len(projects),
            "projects": [
                {
                    "project_id": p.project_id,
                    "project_name": p.project_name,
                    "status": p.status,
                    "updated_at": p.updated_at.isoformat(),
                    "goal": p.frontmatter.research_goal,
                    "tags": p.frontmatter.tags,
                }
                for p in projects
            ],
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@mcp.tool(description="Gets metadata, current state, and index summary for a research project.")
def project_get(project_id: str, vault_root: str | None = None) -> dict[str, Any]:
    try:
        p_svc = get_core_services(vault_root)[0]
        proj = p_svc.get_project(project_id)
        p_dir = p_svc.get_project_dir(project_id)

        state_content = ""
        state_file = p_dir / "STATE.md"
        if state_file.exists():
            state_content = state_file.read_text(encoding="utf-8")

        handoff_content = ""
        handoff_file = p_dir / "HANDOFF.md"
        if handoff_file.exists():
            handoff_content = handoff_file.read_text(encoding="utf-8")

        return {
            "status": "success",
            "project_id": proj.project_id,
            "project_name": proj.project_name,
            "status_field": proj.status,
            "research_goal": proj.frontmatter.research_goal,
            "description": proj.frontmatter.description,
            "created_at": proj.frontmatter.created_at.isoformat(),
            "updated_at": proj.updated_at.isoformat(),
            "tags": proj.frontmatter.tags,
            "state_summary": state_content,
            "handoff_summary": handoff_content,
        }
    except ResearchOSError as exc:
        return {"status": "error", "message": exc.message, "details": exc.details}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# =========================================================================
# 2. Universal Memory Tools
# =========================================================================

@mcp.tool(description="Atomically records a new universal memory (knowledge, decision, hypothesis, observation, negative, reference, handoff).")
def memory_add(
    project_id: str,
    type: str,
    title: str,
    content: str,
    tags: list[str] | None = None,
    source_agent: str | None = None,
    source_skill: str | None = None,
    source_ref: str | None = None,
    related_memory_ids: list[str] | None = None,
    confidence: float | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        m_svc = get_core_services(vault_root)[1]
        mem = m_svc.add_memory(
            project_id=project_id,
            type=type,
            title=title,
            content=content,
            tags=tags,
            source_agent=source_agent,
            source_skill=source_skill,
            source_ref=source_ref,
            related_memory_ids=related_memory_ids,
            confidence=confidence,
        )
        return {
            "status": "success",
            "memory_id": mem.id,
            "project_id": mem.project_id,
            "type": mem.type.value,
            "title": mem.title,
            "file_path": mem.file_path,
            "created_at": mem.created_at.isoformat(),
        }
    except ResearchOSError as exc:
        return {"status": "error", "message": exc.message, "details": exc.details}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@mcp.tool(description="Retrieves a specific memory by its unique ID within a project.")
def memory_get(project_id: str, memory_id: str, vault_root: str | None = None) -> dict[str, Any]:
    try:
        m_svc = get_core_services(vault_root)[1]
        mem = m_svc.get_memory(project_id, memory_id)
        return {
            "status": "success",
            "memory_id": mem.id,
            "project_id": mem.project_id,
            "type": mem.type.value,
            "title": mem.title,
            "status_field": mem.status.value,
            "created_at": mem.created_at.isoformat(),
            "updated_at": mem.updated_at.isoformat(),
            "source_agent": mem.frontmatter.source_agent,
            "source_skill": mem.frontmatter.source_skill,
            "source_ref": mem.frontmatter.source_ref,
            "confidence": mem.frontmatter.confidence,
            "tags": mem.tags,
            "related": mem.related,
            "supersedes": mem.supersedes,
            "file_path": mem.file_path,
            "content": mem.content,
        }
    except ResearchOSError as exc:
        return {"status": "error", "message": exc.message, "details": exc.details}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@mcp.tool(description="Searches memories within a project (or across projects if cross_project=True) with keyword, tag, and type filters.")
def memory_search(
    project_id: str,
    query: str | None = None,
    type: str | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
    limit: int = 20,
    cross_project: bool = False,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        r_svc = get_core_services(vault_root)[2]
        hits = r_svc.search_memories(
            project_id=project_id,
            query=query,
            type=type,
            tags=tags,
            status=status,
            limit=limit,
            cross_project=cross_project,
        )
        return {
            "status": "success",
            "project_id": project_id,
            "total_hits": len(hits),
            "hits": [hit.model_dump() for hit in hits],
        }
    except ResearchOSError as exc:
        return {"status": "error", "message": exc.message, "details": exc.details}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@mcp.tool(description="Updates metadata, confidence, tags, or content of an existing memory safely.")
def memory_update(
    project_id: str,
    memory_id: str,
    title: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
    confidence: float | None = None,
    status: str | None = None,
    related_memory_ids: list[str] | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        m_svc = get_core_services(vault_root)[1]
        mem = m_svc.update_memory(
            project_id=project_id,
            memory_id=memory_id,
            title=title,
            content=content,
            tags=tags,
            confidence=confidence,
            status=status,
            related_memory_ids=related_memory_ids,
        )
        return {
            "status": "success",
            "memory_id": mem.id,
            "project_id": mem.project_id,
            "updated_at": mem.updated_at.isoformat(),
            "status_field": mem.status.value,
        }
    except ResearchOSError as exc:
        return {"status": "error", "message": exc.message, "details": exc.details}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@mcp.tool(description="Supersedes an older memory with a revised memory, recording reason and preserving historical evidence.")
def memory_supersede(
    project_id: str,
    old_memory_id: str,
    title: str,
    content: str,
    reason: str,
    type: str | None = None,
    tags: list[str] | None = None,
    source_agent: str | None = None,
    source_skill: str | None = None,
    source_ref: str | None = None,
    confidence: float | None = None,
    related_memory_ids: list[str] | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        m_svc = get_core_services(vault_root)[1]
        new_mem = m_svc.supersede_memory(
            project_id=project_id,
            old_memory_id=old_memory_id,
            title=title,
            content=content,
            reason=reason,
            type=type,
            tags=tags,
            source_agent=source_agent,
            source_skill=source_skill,
            source_ref=source_ref,
            confidence=confidence,
            related_memory_ids=related_memory_ids,
        )
        return {
            "status": "success",
            "new_memory_id": new_mem.id,
            "superseded_id": old_memory_id,
            "project_id": project_id,
            "file_path": new_mem.file_path,
        }
    except ResearchOSError as exc:
        return {"status": "error", "message": exc.message, "details": exc.details}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@mcp.tool(description="Archives a memory, moving it to archive/ and setting status to archived.")
def memory_archive(
    project_id: str,
    memory_id: str,
    reason: str | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        m_svc = get_core_services(vault_root)[1]
        archived = m_svc.archive_memory(project_id, memory_id, reason=reason)
        return {
            "status": "success",
            "memory_id": archived.id,
            "status_field": archived.status.value,
            "file_path": archived.file_path,
        }
    except ResearchOSError as exc:
        return {"status": "error", "message": exc.message, "details": exc.details}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# =========================================================================
# 3. Context Builder Tool
# =========================================================================

@mcp.tool(description="Builds a prioritized, token-budgeted Markdown context pack (quick, task, or full) citing original file paths.")
def context_build(
    project_id: str,
    task: str | None = None,
    context_mode: str = "quick",
    max_tokens: int = 4000,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        c_bld = get_core_services(vault_root)[3]
        pack = c_bld.build_context(
            project_id=project_id,
            task=task,
            context_mode=context_mode,
            max_tokens=max_tokens,
        )
        return {
            "status": "success",
            "project_id": project_id,
            "context_mode": context_mode,
            "task": task,
            "context_pack": pack,
        }
    except ResearchOSError as exc:
        return {"status": "error", "message": exc.message, "details": exc.details}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# =========================================================================
# 4. Handoff Tools
# =========================================================================

@mcp.tool(description="Records an agent shift handoff, updating HANDOFF.md, STATE.md, and archiving a handoff memory.")
def handoff_create(
    project_id: str,
    task: str,
    completed_work: list[str] | None = None,
    current_progress: str | None = None,
    important_findings: list[str] | None = None,
    decisions_made: list[str] | None = None,
    issues_encountered: list[str] | None = None,
    unresolved_items: list[str] | None = None,
    next_steps: list[str] | None = None,
    related_memory_ids: list[str] | None = None,
    related_files: list[str] | None = None,
    agent_id: str | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        h_svc = get_core_services(vault_root)[4]
        mem = h_svc.create_handoff(
            project_id=project_id,
            task=task,
            completed_work=completed_work,
            current_progress=current_progress,
            important_findings=important_findings,
            decisions_made=decisions_made,
            issues_encountered=issues_encountered,
            unresolved_items=unresolved_items,
            next_steps=next_steps,
            related_memory_ids=related_memory_ids,
            related_files=related_files,
            agent_id=agent_id,
        )
        return {
            "status": "success",
            "handoff_memory_id": mem.id,
            "project_id": project_id,
            "file_path": mem.file_path,
        }
    except ResearchOSError as exc:
        return {"status": "error", "message": exc.message, "details": exc.details}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@mcp.tool(description="Retrieves the latest agent handoff notes from HANDOFF.md.")
def handoff_get(project_id: str, vault_root: str | None = None) -> dict[str, Any]:
    try:
        h_svc = get_core_services(vault_root)[4]
        text = h_svc.get_latest_handoff(project_id)
        return {
            "status": "success",
            "project_id": project_id,
            "handoff_content": text,
        }
    except ResearchOSError as exc:
        return {"status": "error", "message": exc.message, "details": exc.details}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# =========================================================================
# 5. Maintenance Tools
# =========================================================================

@mcp.tool(description="Scans all memory files in a project folder and regenerates INDEX.md completely.")
def index_rebuild(project_id: str, vault_root: str | None = None) -> dict[str, Any]:
    try:
        p_svc = get_core_services(vault_root)[0]
        res = p_svc.rebuild_index(project_id)
        return res
    except ResearchOSError as exc:
        return {"status": "error", "message": exc.message, "details": exc.details}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@mcp.tool(description="Validates schemas of all memories, verifies links, and checks project folder integrity.")
def project_validate(project_id: str, vault_root: str | None = None) -> dict[str, Any]:
    try:
        p_svc = get_core_services(vault_root)[0]
        res = p_svc.validate_project(project_id)
        return res
    except ResearchOSError as exc:
        return {"status": "error", "message": exc.message, "details": exc.details}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# =========================================================================
# Server execution entry point
# =========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="ResearchOS Universal Memory MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()

    if args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
