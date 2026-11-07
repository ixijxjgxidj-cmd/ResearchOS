"""Official Model Context Protocol (MCP) server for ResearchOS."""

import json
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from researchos.config.settings import Settings
from researchos.core.enums import (
    ArtifactRole,
    ClaimStatus,
    ExperimentOutcome,
    ExperimentStatus,
    FindingStatus,
    PaperReadingStatus,
    RunStatus,
)
from researchos.core.exceptions import ResearchOSError
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

mcp = MCPServer(
    name="researchos",
    description="Autonomous scientific research persistent memory, experiment management, and evidence traceability.",
)


def get_services(vault_root: str | None = None) -> tuple[
    ProjectService,
    ExperimentService,
    RunService,
    PaperService,
    ArtifactService,
    FindingService,
    ClaimService,
    ContextService,
    HandoffService,
    AuditService,
]:
    root = Settings.discover_vault_root(vault_root)
    return (
        ProjectService(root),
        ExperimentService(root),
        RunService(root),
        PaperService(root),
        ArtifactService(root),
        FindingService(root),
        ClaimService(root),
        ContextService(root),
        HandoffService(root),
        AuditService(root),
    )


# 1. Project Tools
@mcp.tool(description="Creates a new research project in the vault with standardized directories and tracking files.")
def research_project_create(
    name: str,
    research_question: str | None = None,
    objectives: list[str] | None = None,
    scope: str | None = None,
    members: list[str] | None = None,
    repositories: list[str] | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        p_svc = get_services(vault_root)[0]
        proj = p_svc.create_project(
            name=name,
            research_question=research_question,
            objectives=objectives,
            scope=scope,
            members=members,
            repositories=repositories,
        )
        path = p_svc.store.resolve_entity_path(proj.id)
        return {
            "status": "success",
            "id": proj.id,
            "path": str(path),
            "project": proj.model_dump(mode="json"),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool(description="Lists all research projects currently tracked in the ResearchVault.")
def research_project_list(vault_root: str | None = None) -> dict[str, Any]:
    try:
        p_svc = get_services(vault_root)[0]
        projects = p_svc.list_projects()
        return {
            "status": "success",
            "count": len(projects),
            "projects": [p.model_dump(mode="json") for p in projects],
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool(description="Retrieves full metadata and markdown body of a research project.")
def research_project_get(project_id: str, vault_root: str | None = None) -> dict[str, Any]:
    try:
        p_svc = get_services(vault_root)[0]
        proj, body = p_svc.get_project(project_id)
        path = p_svc.store.resolve_entity_path(proj.id)
        return {
            "status": "success",
            "id": proj.id,
            "path": str(path),
            "project": proj.model_dump(mode="json"),
            "content": body,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool(description="Fetches project status summary, run metrics, and handoff pointers.")
def research_project_status(project_id: str, vault_root: str | None = None) -> dict[str, Any]:
    try:
        p_svc = get_services(vault_root)[0]
        status = p_svc.get_project_status(project_id)
        return {"status": "success", "id": project_id, **status}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# 2. Experiment Tools
@mcp.tool(description="Designs and registers a new experiment plan under a project.")
def research_experiment_create(
    project_id: str,
    title: str,
    objective: str | None = None,
    research_question: str | None = None,
    hypothesis: str | None = None,
    rationale: str | None = None,
    literature: list[str] | None = None,
    execution: dict[str, Any] | None = None,
    method: str | None = None,
    planned_parameters: dict[str, Any] | None = None,
    expected_result: str | None = None,
    success_criteria: list[str] | None = None,
    inputs: list[str] | None = None,
    planned_outputs: list[str] | None = None,
    is_exploratory: bool = False,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        _, e_svc, *_ = get_services(vault_root)
        exp = e_svc.create_experiment(
            project_id=project_id,
            title=title,
            objective=objective,
            research_question=research_question,
            hypothesis=hypothesis,
            rationale=rationale,
            literature=literature,
            execution=execution,
            method=method,
            planned_parameters=planned_parameters,
            expected_result=expected_result,
            success_criteria=success_criteria,
            inputs=inputs,
            planned_outputs=planned_outputs,
            is_exploratory=is_exploratory,
        )
        path = e_svc.store.resolve_entity_path(exp.id, project_id=project_id)
        return {
            "status": "success",
            "id": exp.id,
            "path": str(path),
            "experiment": exp.model_dump(mode="json"),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool(description="Retrieves experiment specifications, hypotheses, parameters, and findings.")
def research_experiment_get(experiment_id: str, vault_root: str | None = None) -> dict[str, Any]:
    try:
        _, e_svc, *_ = get_services(vault_root)
        exp, body = e_svc.get_experiment(experiment_id)
        path = e_svc.store.resolve_entity_path(exp.id, project_id=exp.project_id)
        return {
            "status": "success",
            "id": exp.id,
            "path": str(path),
            "experiment": exp.model_dump(mode="json"),
            "content": body,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool(description="Lists experiments filtered optionally by project ID and status.")
def research_experiment_list(
    project_id: str | None = None,
    status: str | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        _, e_svc, *_ = get_services(vault_root)
        st_enum = ExperimentStatus(status) if status else None
        exps = e_svc.list_experiments(project_id=project_id, status=st_enum)
        return {
            "status": "success",
            "count": len(exps),
            "experiments": [e.model_dump(mode="json") for e in exps],
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool(description="Updates experiment state or specifications with audit tracking of parameter changes.")
def research_experiment_update(
    experiment_id: str,
    updates: dict[str, Any],
    reason: str | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        _, e_svc, *_ = get_services(vault_root)
        exp = e_svc.update_experiment(experiment_id=experiment_id, updates=updates, reason=reason)
        path = e_svc.store.resolve_entity_path(exp.id, project_id=exp.project_id)
        return {
            "status": "success",
            "id": exp.id,
            "path": str(path),
            "experiment": exp.model_dump(mode="json"),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool(description="Runs preflight readiness check on an experiment before moving it to ready.")
def research_experiment_validate(experiment_id: str, vault_root: str | None = None) -> dict[str, Any]:
    try:
        _, e_svc, *_ = get_services(vault_root)
        res = e_svc.validate_preflight(experiment_id)
        return {"status": "success", **res}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# 3. Run Tools
@mcp.tool(description="Spawns an execution run for an experiment, recording agent identity and execution host.")
def research_run_create(
    experiment_id: str,
    agent_name: str,
    session_id: str | None = None,
    executor_type: str = "local",
    server_id: str | None = None,
    server_task_id: str | None = None,
    infrastructure_provider: str | None = None,
    working_directory: str | None = None,
    actual_parameters: dict[str, Any] | None = None,
    random_seed: int | None = None,
    code_repository: str | None = None,
    code_commit: str | None = None,
    environment: dict[str, Any] | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        _, _, r_svc, *_ = get_services(vault_root)
        r = r_svc.create_run(
            experiment_id=experiment_id,
            agent_name=agent_name,
            session_id=session_id,
            executor_type=executor_type,
            server_id=server_id,
            server_task_id=server_task_id,
            infrastructure_provider=infrastructure_provider,
            working_directory=working_directory,
            actual_parameters=actual_parameters,
            random_seed=random_seed,
            code_repository=code_repository,
            code_commit=code_commit,
            environment=environment,
        )
        path = r_svc.store.resolve_entity_path(r.id, project_id=r.project_id)
        return {
            "status": "success",
            "id": r.id,
            "path": str(path),
            "run": r.model_dump(mode="json"),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool(description="Retrieves execution run details, actual parameters, and telemetry metrics.")
def research_run_get(run_id: str, vault_root: str | None = None) -> dict[str, Any]:
    try:
        _, _, r_svc, *_ = get_services(vault_root)
        r, body = r_svc.get_run(run_id)
        path = r_svc.store.resolve_entity_path(r.id, project_id=r.project_id)
        return {
            "status": "success",
            "id": r.id,
            "path": str(path),
            "run": r.model_dump(mode="json"),
            "content": body,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool(description="Updates intermediate run telemetry, working directory, or environment fingerprints.")
def research_run_update(run_id: str, updates: dict[str, Any], vault_root: str | None = None) -> dict[str, Any]:
    try:
        _, _, r_svc, *_ = get_services(vault_root)
        r = r_svc.update_run(run_id=run_id, updates=updates)
        path = r_svc.store.resolve_entity_path(r.id, project_id=r.project_id)
        return {
            "status": "success",
            "id": r.id,
            "path": str(path),
            "run": r.model_dump(mode="json"),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool(description="Finalizes an experimental run, records actual parameters, telemetry, and backfills experiment findings.")
def research_run_complete(
    run_id: str,
    actual_parameters: dict[str, Any],
    status: str = "succeeded",
    experiment_outcome: str | None = None,
    metrics: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    deviations: list[str] | None = None,
    result_summary: str | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        _, _, r_svc, *_ = get_services(vault_root)
        st_enum = RunStatus(status)
        oc_enum = ExperimentOutcome(experiment_outcome) if experiment_outcome else None
        r = r_svc.complete_run(
            run_id=run_id,
            status=st_enum,
            actual_parameters=actual_parameters,
            metrics=metrics,
            errors=errors,
            warnings=warnings,
            deviations=deviations,
            result_summary=result_summary,
            experiment_outcome=oc_enum,
        )
        path = r_svc.store.resolve_entity_path(r.id, project_id=r.project_id)
        return {
            "status": "success",
            "id": r.id,
            "path": str(path),
            "run": r.model_dump(mode="json"),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# 4. Paper Tools
@mcp.tool(description="Registers a paper literature markdown note in the vault (no Zotero required).")
def research_paper_create(
    title: str,
    citekey: str,
    authors: list[str] | None = None,
    year: int | None = None,
    journal: str | None = None,
    doi: str | None = None,
    url: str | None = None,
    pdf_path: str | None = None,
    abstract: str | None = None,
    reading_status: str = "to_read",
    projects: list[str] | None = None,
    related_experiments: list[str] | None = None,
    tags: list[str] | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        *_, p_svc, _, _, _, _, _, _ = get_services(vault_root)
        st_enum = PaperReadingStatus(reading_status)
        paper = p_svc.create_paper(
            title=title,
            citekey=citekey,
            authors=authors,
            year=year,
            journal=journal,
            doi=doi,
            url=url,
            pdf_path=pdf_path,
            abstract=abstract,
            reading_status=st_enum,
            projects=projects,
            related_experiments=related_experiments,
            tags=tags,
        )
        path = p_svc.store.resolve_entity_path(paper.id)
        return {
            "status": "success",
            "id": paper.id,
            "path": str(path),
            "paper": paper.model_dump(mode="json"),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool(description="Retrieves paper notes and annotations by Paper ID or Citekey.")
def research_paper_get(identifier: str, vault_root: str | None = None) -> dict[str, Any]:
    try:
        *_, p_svc, _, _, _, _, _, _ = get_services(vault_root)
        paper, body = p_svc.get_paper(identifier)
        path = p_svc.store.resolve_entity_path(paper.id)
        return {
            "status": "success",
            "id": paper.id,
            "path": str(path),
            "paper": paper.model_dump(mode="json"),
            "content": body,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool(description="Searches literature records across titles, abstracts, authors, and citekeys.")
def research_paper_search(
    query: str,
    tags: list[str] | None = None,
    reading_status: str | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        *_, p_svc, _, _, _, _, _, _ = get_services(vault_root)
        st_enum = PaperReadingStatus(reading_status) if reading_status else None
        results = p_svc.search_papers(query=query, tags=tags, reading_status=st_enum)
        return {
            "status": "success",
            "count": len(results),
            "papers": [p.model_dump(mode="json") for p in results],
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# 5. Artifact Tool
@mcp.tool(description="Registers an execution artifact, computing its cryptographic SHA-256 hash.")
def research_artifact_register(
    run_id: str,
    path: str,
    role: str = "metrics",
    name: str | None = None,
    storage_backend: str = "local",
    server_id: str | None = None,
    media_type: str | None = None,
    sha256: str | None = None,
    size_bytes: int | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        *_, art_svc, _, _, _, _, _ = get_services(vault_root)
        art = art_svc.register_artifact(
            run_id=run_id,
            path=path,
            role=role,
            name=name,
            storage_backend=storage_backend,
            server_id=server_id,
            media_type=media_type,
            sha256=sha256,
            size_bytes=size_bytes,
        )
        art_path = art_svc.store.resolve_entity_path(art.id)
        return {
            "status": "success",
            "id": art.id,
            "path": str(art_path),
            "artifact": art.model_dump(mode="json"),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# 6. Finding & Claim Tools
@mcp.tool(description="Formulates an empirical scientific finding linked to an experiment, run, or artifacts.")
def research_finding_create(
    project_id: str,
    experiment_id: str,
    title: str,
    summary: str | None = None,
    run_id: str | None = None,
    evidence_artifacts: list[str] | None = None,
    literature: list[str] | None = None,
    research_question: str | None = None,
    status: str = "candidate",
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        *_, find_svc, _, _, _, _ = get_services(vault_root)
        st_enum = FindingStatus(status)
        finding = find_svc.create_finding(
            project_id=project_id,
            experiment_id=experiment_id,
            title=title,
            summary=summary,
            run_id=run_id,
            evidence_artifacts=evidence_artifacts,
            literature=literature,
            research_question=research_question,
            status=st_enum,
        )
        path = find_svc.store.resolve_entity_path(finding.id, project_id=project_id)
        return {
            "status": "success",
            "id": finding.id,
            "path": str(path),
            "finding": finding.model_dump(mode="json"),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool(description="Creates a scientific claim for publication, specifying supporting and contradicting evidence.")
def research_claim_create(
    project_id: str,
    text: str,
    status: str = "unverified",
    supporting_experiments: list[str] | None = None,
    supporting_runs: list[str] | None = None,
    contradicting_experiments: list[str] | None = None,
    literature: list[str] | None = None,
    artifacts: list[str] | None = None,
    limitations: list[str] | None = None,
    scope: str | None = None,
    manuscript_section: str | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        *_, claim_svc, _, _, _ = get_services(vault_root)
        st_enum = ClaimStatus(status)
        claim = claim_svc.create_claim(
            project_id=project_id,
            text=text,
            status=st_enum,
            supporting_experiments=supporting_experiments,
            supporting_runs=supporting_runs,
            contradicting_experiments=contradicting_experiments,
            literature=literature,
            artifacts=artifacts,
            limitations=limitations,
            scope=scope,
            manuscript_section=manuscript_section,
        )
        path = claim_svc.store.resolve_entity_path(claim.id, project_id=project_id)
        return {
            "status": "success",
            "id": claim.id,
            "path": str(path),
            "claim": claim.model_dump(mode="json"),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# 7. Context Builder Tool
@mcp.tool(description="Assembles a complete, self-contained Markdown Research Context Pack for an experiment or project.")
def research_context_build(target_id: str, vault_root: str | None = None) -> dict[str, Any]:
    try:
        *_, ctx_svc, _, _ = get_services(vault_root)
        pack_md = ctx_svc.build_context(target_id)
        return {
            "status": "success",
            "id": target_id,
            "context_pack": pack_md,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# 8. Handoff Tool
@mcp.tool(description="Updates project HANDOFF.md and STATUS.md before ending an agent session.")
def research_handoff_update(
    project_id: str,
    current_focus: str,
    completed_since_last: list[str] | None = None,
    modified_files: list[str] | None = None,
    open_issues: list[str] | None = None,
    next_steps: list[str] | None = None,
    target_files_for_next_agent: list[str] | None = None,
    vault_root: str | None = None,
) -> dict[str, Any]:
    try:
        *_, handoff_svc, _ = get_services(vault_root)
        content = handoff_svc.update_handoff(
            project_id=project_id,
            current_focus=current_focus,
            completed_since_last=completed_since_last,
            modified_files=modified_files,
            open_issues=open_issues,
            next_steps=next_steps,
            target_files_for_next_agent=target_files_for_next_agent,
        )
        return {
            "status": "success",
            "id": project_id,
            "handoff_content": content,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# 9. Audit Tool
@mcp.tool(description="Runs referential integrity, unverified claims, negative result citation, and artifact verification.")
def research_audit(project_id: str | None = None, vault_root: str | None = None) -> dict[str, Any]:
    try:
        *_, audit_svc = get_services(vault_root)
        report = audit_svc.run_audit(project_id=project_id)
        return report
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def main() -> None:
    """Entry point for STDIO MCP server."""
    mcp.run("stdio")


if __name__ == "__main__":
    main()
