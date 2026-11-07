# ResearchOS Implementation Plan

## 1. Project Overview & Architectural Boundaries

ResearchOS is an autonomous, agent-agnostic, and Obsidian-optional scientific research management framework. It provides persistent memory, experimental workflow management, evidence traceability, and context re-hydration across disparate LLM agents (Claude Code, OpenAI Codex, Gemini CLI, Cursor, OpenCode, etc.), sessions, and execution environments.

### Unbreakable Constraints
- **Markdown-first**: All research objects are saved as plain Markdown files with YAML Frontmatter and relative Markdown links. No single point of truth in relational or vector DBs.
- **Filesystem-first**: The filesystem directory structure is the single source of truth. Valid Markdown readable by standard editors even without ResearchOS.
- **Agent-independent**: Standardized MCP tools and CLI commands with identical business logic.
- **Obsidian-optional**: No dependency on Obsidian, Dataview, or custom plugins. Obsidian is only an optional viewer.
- **No Zotero Dependency**: Papers are standalone Markdown files in `01-Literature/`. PDFs can be stored locally or referenced by path.
- **DSH Reuse**: Decoupled from GPU server management. DSH handles GPU provisioning/lifecycle/backup; ResearchOS records experiments, runs, and metadata via agent coordination. No credentials (SSH keys, passwords, API tokens) are ever stored.

---

## 2. Directory Structure & Layout

The project workspace will follow the exact specification:

```text
d:\reasearch os/
├── pyproject.toml
├── uv.lock
├── README.md
├── LICENSE
├── .gitignore
├── AGENTS.md
│
├── src/
│   └── researchos/
│       ├── __init__.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── enums.py
│       │   ├── ids.py
│       │   └── exceptions.py
│       │
│       ├── services/
│       │   ├── __init__.py
│       │   ├── project_service.py
│       │   ├── experiment_service.py
│       │   ├── run_service.py
│       │   ├── paper_service.py
│       │   ├── finding_service.py
│       │   ├── claim_service.py
│       │   ├── artifact_service.py
│       │   ├── context_service.py
│       │   ├── validation_service.py
│       │   ├── audit_service.py
│       │   └── handoff_service.py
│       │
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── markdown_store.py
│       │   ├── frontmatter.py
│       │   ├── atomic_writer.py
│       │   ├── file_lock.py
│       │   └── link_resolver.py
│       │
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── mcp_server.py
│       │   └── cli.py
│       │
│       ├── integration/
│       │   ├── __init__.py
│       │   └── dsh/
│       │       ├── __init__.py
│       │       ├── README.md
│       │       ├── mapping.md
│       │       └── mock_adapter.py
│       │
│       └── config/
│           ├── __init__.py
│           └── settings.py
│
├── schemas/
│   ├── project.schema.json
│   ├── experiment.schema.json
│   ├── run.schema.json
│   ├── paper.schema.json
│   ├── finding.schema.json
│   ├── claim.schema.json
│   ├── artifact.schema.json
│   └── decision.schema.json
│
├── templates/
│   ├── project.md
│   ├── experiment.md
│   ├── run.md
│   ├── paper.md
│   ├── finding.md
│   ├── claim.md
│   ├── artifact.md
│   └── decision.md
│
├── skills/
│   ├── research-bootstrap/
│   │   └── SKILL.md
│   ├── experiment-planning/
│   │   └── SKILL.md
│   ├── experiment-execution/
│   │   └── SKILL.md
│   ├── experiment-review/
│   │   └── SKILL.md
│   ├── literature-review/
│   │   └── SKILL.md
│   ├── research-handoff/
│   │   └── SKILL.md
│   └── manuscript-writing/
│       └── SKILL.md
│
├── examples/
│   └── example-vault/
│       ├── AGENTS.md
│       ├── 00-Projects/
│       ├── 01-Literature/
│       ├── 02-Knowledge/
│       └── 90-Templates/
│
├── docs/
│   ├── IMPLEMENTATION_PLAN.md
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   ├── WORKFLOW.md
│   ├── MCP_REFERENCE.md
│   ├── CLI_REFERENCE.md
│   ├── DSH_INTEGRATION.md
│   ├── AGENT_RULES.md
│   ├── INSTALLATION.md
│   └── FINAL_ACCEPTANCE_REPORT.md
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_ids.py
    ├── test_frontmatter.py
    ├── test_project.py
    ├── test_experiment.py
    ├── test_run.py
    ├── test_paper.py
    ├── test_artifact.py
    ├── test_context.py
    ├── test_validation.py
    ├── test_audit.py
    ├── test_concurrency.py
    ├── test_mcp.py
    └── test_cli.py
```

---

## 3. Core Modules & Implementation Details

### 3.1 ID Generation (`src/researchos/core/ids.py`)
- Pattern: `{PREFIX}-{YYYY}-{NNN}` (e.g. `PRJ-2026-001`, `EXP-2026-001`, `RUN-2026-001`, `PAPER-2026-001`, `FIND-2026-001`, `CLAIM-2026-001`, `ART-2026-001`, `DEC-2026-001`).
- Atomic counter persistence via file-locking in `.researchos/locks/id_sequence.lock` and `.researchos/sequences.json` with fallback filesystem scanning to guarantee monotonic, collision-free concurrent allocations.

### 3.2 Storage Engine (`src/researchos/storage/`)
- `atomic_writer.py`: Writes to a sibling temp file (`.tmp.XXXX`), flushes, fsyncs, and replaces atomically using `os.replace`.
- `file_lock.py`: Cross-platform lock mechanism (using `portalocker` or file-descriptor locking on Windows/POSIX) with re-entrancy protection and timeouts.
- `frontmatter.py`: Strict YAML parser/serializer using `yaml.SafeLoader` and `yaml.SafeDumper`, preserving UTF-8, handling YAML header + Markdown body cleanly.
- `markdown_store.py`: CRUD operations for entities with optimistic locking (checking `updated_at` or version hashes), path validation (preventing directory traversal outside the vault root), and title update logic (e.g., adding " (未结项)" to H1 titles when not completed).
- `link_resolver.py`: Calculates standard relative markdown links (e.g. `../../01-Literature/PAPER-2026-001.md`) between entities.

### 3.3 Core Models (`src/researchos/core/models.py`)
Pydantic v2 models matching PART 4 of the specification:
- `Project`: id, name, status, research_question, objectives, scope, members, repositories, literature, experiments, claims, created_at, updated_at, body sections.
- `Experiment`: id, project_id, title, status, outcome, objective, research_question, hypothesis, rationale, literature, execution, method, planned_parameters, expected_result, success_criteria, inputs, planned_outputs, runs, findings, created_at, updated_at, body sections.
- `Run`: id, project_id, experiment_id, status, agent_name, session_id, executor_type, server_id, working_directory, started_at, finished_at, actual_parameters, random_seed, code_repository, code_commit, environment, inputs, artifacts, metrics, errors, warnings, deviations, result_summary.
- `Paper`: id, citekey, title, authors, year, journal, doi, url, pdf_path, abstract, reading_status, projects, related_experiments, body sections.
- `Finding`: id, project_id, experiment_id, run_id, title, summary, evidence_artifacts, literature, status, created_at, updated_at.
- `Claim`: id, project_id, text, status, supporting_experiments, supporting_runs, contradicting_experiments, literature, artifacts, limitations, scope, manuscript_section.
- `Artifact`: id, run_id, name, role, storage_backend, path, server_id, media_type, size_bytes, sha256, created_at, immutable.
- `Decision`: id, project_id, title, context, decision, consequences, date, author.

### 3.4 Services (`src/researchos/services/`)
- `project_service.py`: Initializes Vault, creates project folders, STATUS.md, HANDOFF.md, CHANGELOG.md, updates dashboards.
- `experiment_service.py`: Creates/updates experiment plans, validates transitions, prevents silent overwriting, enforces preflight checks before `ready`.
- `run_service.py`: Tracks runs, ensures planned parameters != actual parameters, marks success/fail/interrupted, links artifacts.
- `paper_service.py`: Manages literature notes without Zotero, searches by citekey/doi/title/tag.
- `artifact_service.py`: Computes SHA-256, validates file sizes, registers artifacts with immutability flags.
- `context_service.py`: Context Builder that assembles a `Research Context Pack` Markdown string for an experiment/project without needing full project history or chat logs.
- `validation_service.py`: Enforces lifecycle state transitions, validates references, ensures plan vs actual segregation.
- `audit_service.py`: Verifies integrity across vault (dangling links, unreferenced runs, negative outcomes ignored by claims, unverified claims, status mismatches).
- `handoff_service.py`: Updates `HANDOFF.md` with modified files, open problems, next tasks, and pointers for subsequent agents.

### 3.5 Adapters (`src/researchos/adapters/`)
- `cli.py`: Typer CLI implementing all specified commands with `--vault`, `--json`, and rich terminal outputs.
- `mcp_server.py`: Official MCP Python SDK server exposing all required tools over STDIO, sharing identical service instances with CLI.

### 3.6 DSH Integration (`src/researchos/integration/dsh/`)
- Integration documentation and mapping based on the actual schema of `dsh-mcp-server` (`claim_server`, `release_server`, `plan_server_backup`, `plan_task_allocation`, `register_dataset`, `query_troubleshooting`, etc.).
- A Mock Adapter for testing the multi-agent workflow in environments where live DSH server is unreachable.

---

## 4. Phase-by-Phase Execution Schedule

- **Phase 1: Environment & Project Setup**
  - Git repository initialization (done).
  - `pyproject.toml` with dependencies (`pydantic>=2.0`, `pyyaml`, `typer>=0.9.0`, `mcp>=1.0.0`, `portalocker`, `rich`, `pytest`).
  - Run `uv sync` / `uv pip install` to produce `uv.lock`.
- **Phase 2: Core Storage & Foundation Models**
  - Enums & IDs with atomic counter & file lock.
  - Frontmatter parser & atomic file writer.
  - Pydantic models & JSON schemas generation.
  - Markdown templates.
- **Phase 3: Service Layer**
  - ProjectService, ExperimentService, RunService, PaperService, ArtifactService, FindingService, ClaimService, ContextService, ValidationService, AuditService, HandoffService.
  - Vault dashboard generator.
- **Phase 4: CLI Interface**
  - Complete Typer CLI commands matching prompt Part 9.
- **Phase 5: MCP Server**
  - Standard MCP server exposing tools matching prompt Part 8.
- **Phase 6: Agent Skills & AGENTS.md**
  - 7 standard skills in `skills/` and root `AGENTS.md`.
- **Phase 7: DSH Documentation & Mocking**
  - `docs/DSH_INTEGRATION.md`, mapping, mock tests.
- **Phase 8: Comprehensive Test Suite**
  - Tests A through J in `tests/`.
  - Fix any defects until 100% passing.
- **Phase 9: Documentation & Example Vault**
  - Architecture, data models, user manuals, CLI/MCP references, example vault.
- **Phase 10: Final Acceptance & Report**
  - Verify every single acceptance criterion.
  - Produce `docs/FINAL_ACCEPTANCE_REPORT.md` and complete dev report.
