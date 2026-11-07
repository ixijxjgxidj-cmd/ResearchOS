# ResearchOS Model Context Protocol (MCP) Reference

The ResearchOS MCP server operates over standard STDIO transport. All tools invoke the unified Service Layer and guarantee input validation, path security, and credential redaction.

## Tool Catalog

### 1. Project Management
- `research_project_create`: Creates a new research project.
  - Parameters: `name` (str, req), `research_question` (str), `objectives` (list[str]), `scope` (str), `members` (list[str]), `repositories` (list[str]), `vault_root` (str).
- `research_project_list`: Lists all projects.
- `research_project_get`: Retrieves full project metadata and body.
  - Parameters: `project_id` (str, req).
- `research_project_status`: Summarizes run velocity and handoff pointers.
  - Parameters: `project_id` (str, req).

### 2. Experiment Management
- `research_experiment_create`: Creates an experiment design.
  - Parameters: `project_id` (str, req), `title` (str, req), `objective` (str), `hypothesis` (str), `method` (str), `planned_parameters` (dict), `expected_result` (str), `success_criteria` (list[str]), `is_exploratory` (bool).
- `research_experiment_get`: Retrieves experiment specification.
  - Parameters: `experiment_id` (str, req).
- `research_experiment_list`: Lists experiments optionally filtered by project and status.
  - Parameters: `project_id` (str), `status` (str).
- `research_experiment_update`: Updates experiment state and records parameter change warnings.
  - Parameters: `experiment_id` (str, req), `updates` (dict, req), `reason` (str).
- `research_experiment_validate`: Runs preflight check before moving to ready.
  - Parameters: `experiment_id` (str, req).

### 3. Run Execution & Telemetry
- `research_run_create`: Initializes an execution run.
  - Parameters: `experiment_id` (str, req), `agent_name` (str, req), `executor_type` (str), `server_id` (str), `working_directory` (str), `code_repository` (str), `code_commit` (str).
- `research_run_get`: Retrieves run details and execution telemetry.
  - Parameters: `run_id` (str, req).
- `research_run_update`: Updates intermediate progress.
  - Parameters: `run_id` (str, req), `updates` (dict, req).
- `research_run_complete`: Completes a run, records actual parameters, metrics, deviations, and outcome.
  - Parameters: `run_id` (str, req), `actual_parameters` (dict, req), `status` (str), `experiment_outcome` (str), `metrics` (dict), `errors` (list[str]), `deviations` (list[str]), `result_summary` (str).

### 4. Literature (No Zotero)
- `research_paper_create`: Registers a paper note.
  - Parameters: `title` (str, req), `citekey` (str, req), `authors` (list[str]), `year` (int), `doi` (str), `abstract` (str), `reading_status` (str), `projects` (list[str]).
- `research_paper_get`: Retrieves paper by ID or citekey.
  - Parameters: `identifier` (str, req).
- `research_paper_search`: Searches papers across titles, citekeys, and abstracts.
  - Parameters: `query` (str, req), `tags` (list[str]), `reading_status` (str).

### 5. Artifacts
- `research_artifact_register`: Computes SHA-256 and registers an artifact.
  - Parameters: `run_id` (str, req), `path` (str, req), `role` (str, req), `name` (str), `storage_backend` (str).

### 6. Findings & Claims
- `research_finding_create`: Registers empirical findings.
  - Parameters: `project_id` (str, req), `experiment_id` (str, req), `title` (str, req), `summary` (str), `evidence_artifacts` (list[str]).
- `research_claim_create`: Registers publication-ready claims.
  - Parameters: `project_id` (str, req), `text` (str, req), `status` (str), `supporting_experiments` (list[str]), `contradicting_experiments` (list[str]), `limitations` (list[str]).

### 7. Context Builder & Handoff
- `research_context_build`: Generates deterministic Markdown Context Pack for an experiment or project.
  - Parameters: `target_id` (str, req).
- `research_handoff_update`: Updates `HANDOFF.md` and `STATUS.md`.
  - Parameters: `project_id` (str, req), `current_focus` (str, req), `completed_since_last` (list[str]), `modified_files` (list[str]), `open_issues` (list[str]), `next_steps` (list[str]).

### 8. Audit
- `research_audit`: Full referential integrity, unverified claims, negative outcome, and artifact hash verification.
  - Parameters: `project_id` (str, optional).
