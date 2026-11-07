# ResearchOS Data Model Specification

## 1. Universal Entity Header

Every entity managed by ResearchOS is persisted as a UTF-8 Markdown file containing structured YAML frontmatter:

```yaml
---
schema_version: 1
id: PREFIX-YYYY-NNN
kind: project | experiment | run | paper | finding | claim | artifact | decision
created_at: 2026-11-07T14:00:00Z
updated_at: 2026-11-07T14:30:00Z
---
```

---

## 2. Entity Schemas & Fields

### 2.1 Project (`PRJ-YYYY-NNN`)
- **Location**: `00-Projects/{PRJ-ID}/PROJECT.md`
- **Fields**:
  - `name` (str): Project title.
  - `status` (`active` | `paused` | `completed` | `archived`).
  - `research_question` (str | null): Primary research inquiry.
  - `objectives` (list[str]): Key milestones.
  - `scope` (str | null): Scientific boundaries.
  - `members` (list[str]): Collaborating agents/researchers.
  - `repositories` (list[str]): Associated codebases.
  - `literature` (list[str]): Linked Paper IDs.
  - `experiments` (list[str]): Child Experiment IDs.
  - `claims` (list[str]): Formulated scientific claims.

### 2.2 Experiment (`EXP-YYYY-NNN`)
- **Location**: `00-Projects/{PRJ-ID}/Experiments/{EXP-ID}.md`
- **Fields**:
  - `project_id` (str): Parent Project ID.
  - `title` (str): Experiment title.
  - `status` (`planned` | `ready` | `running` | `blocked` | `needs_review` | `completed` | `abandoned`).
  - `outcome` (`pending` | `positive` | `negative` | `inconclusive` | `failed` | `invalid`).
  - `is_exploratory` (bool): True for early exploratory experiments.
  - `objective` (str | null): Specific technical goal.
  - `hypothesis` (str | null): Scientific hypothesis.
  - `rationale` (str | null): Theoretical motivation.
  - `method` (str | null): Implementation approach.
  - `planned_parameters` (dict): Planned hyperparameters.
  - `expected_result` (str | null): Anticipated findings.
  - `success_criteria` (list[str]): Concrete quantitative criteria.
  - `runs` (list[str]): Associated Run IDs.
  - `findings` (list[str]): Extracted Finding IDs.

### 2.3 Run (`RUN-YYYY-NNN`)
- **Location**: `00-Projects/{PRJ-ID}/Runs/{RUN-ID}.md`
- **Fields**:
  - `project_id` (str)
  - `experiment_id` (str)
  - `status` (`created` | `queued` | `running` | `succeeded` | `failed` | `cancelled` | `interrupted` | `needs_review` | `reviewed`).
  - `agent_name` (str): Identity of the executing agent.
  - `executor_type` (`local` | `dsh`).
  - `server_id` (str | null): Remote host ID if running on DSH.
  - `server_task_id` (str | null): DSH lease ID.
  - `infrastructure_provider` (str | null): e.g. `"dsh"`.
  - `working_directory` (str | null): Isolated execution path.
  - `started_at` (datetime)
  - `finished_at` (datetime | null)
  - `actual_parameters` (dict): Real execution parameters.
  - `random_seed` (int | null)
  - `code_repository` (str | null)
  - `code_commit` (str | null)
  - `environment` (dict): Python, CUDA, OS details.
  - `artifacts` (list[str]): Artifact IDs produced.
  - `metrics` (dict): Final numerical metrics.
  - `errors` (list[str]): Error messages if failed.
  - `deviations` (list[str]): Deviations from planned parameters.
  - `result_summary` (str | null): Summary of execution.

### 2.4 Paper (`PAPER-YYYY-NNN`)
- **Location**: `01-Literature/{PAPER-ID}.md`
- **Fields**:
  - `citekey` (str): BibTeX key.
  - `title` (str)
  - `authors` (list[str])
  - `year` (int | null)
  - `journal` (str | null)
  - `doi` (str | null)
  - `url` (str | null)
  - `pdf_path` (str | null)
  - `abstract` (str | null)
  - `reading_status` (`to_read` | `reading` | `read` | `synthesized` | `partial`).
  - `projects` (list[str])
  - `related_experiments` (list[str])

### 2.5 Artifact (`ART-YYYY-NNN`)
- **Location**: `00-Projects/{PRJ-ID}/Artifacts/{ART-ID}.md`
- **Fields**:
  - `run_id` (str): Originating Run.
  - `name` (str): Artifact name.
  - `role` (`raw_data` | `dataset` | `config` | `source_code` | `log` | `metrics` | `figure` | `checkpoint` | `report`).
  - `storage_backend` (str): `"local"`, `"dsh"`, `"gdrive"`.
  - `path` (str): File path.
  - `size_bytes` (int)
  - `sha256` (str): Cryptographic SHA-256 hash.
  - `immutable` (bool): True.

### 2.6 Finding (`FIND-YYYY-NNN`)
- **Location**: `00-Projects/{PRJ-ID}/Findings/{FIND-ID}.md`
- **Fields**:
  - `project_id` (str)
  - `experiment_id` (str)
  - `run_id` (str | null)
  - `title` (str): Concise finding statement.
  - `status` (`candidate` | `verified` | `rejected`).
  - `evidence_artifacts` (list[str]): Supporting Artifact IDs.
  - `literature` (list[str]): Supporting Paper IDs.

### 2.7 Claim (`CLAIM-YYYY-NNN`)
- **Location**: `00-Projects/{PRJ-ID}/Claims/{CLAIM-ID}.md`
- **Fields**:
  - `project_id` (str)
  - `text` (str): Formal scientific proposition.
  - `status` (`unverified` | `supported` | `contradicted` | `partially_supported` | `abandoned`).
  - `supporting_experiments` (list[str])
  - `supporting_runs` (list[str])
  - `contradicting_experiments` (list[str]): Negative or boundary results.
  - `literature` (list[str])
  - `artifacts` (list[str])
  - `limitations` (list[str])
  - `manuscript_section` (str | null)
