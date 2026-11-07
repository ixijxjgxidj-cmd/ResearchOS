# ResearchOS Model Context Protocol (MCP) Reference

ResearchOS exposes a standardized MCP server interface enabling LLM Agents to manage and query persistent long-term research memory.

Server transport supports both `stdio` and `sse`.

---

## 1. Project Management Tools

### `project_create`
Idempotently creates a new independent project folder with standard subdirectories and documents.
- **Parameters**:
  - `name` (string, required): Human-readable project title.
  - `project_id` (string, optional): Explicit directory ID/slug (auto-generated if omitted).
  - `description` (string, optional): Short project summary.
  - `research_goal` (string, optional): Core scientific objective.
  - `tags` (list[string], optional): Classification tags.
  - `vault_root` (string, optional): Path to vault root.
- **Returns**: `{"status": "success", "project_id": "...", "project_dir": "...", ...}`

### `project_list`
Lists all independent research projects in the vault.
- **Parameters**:
  - `vault_root` (string, optional)
- **Returns**: `{"status": "success", "total": 2, "projects": [...]}`

### `project_get`
Retrieves project metadata, current state summary, and latest handoff.
- **Parameters**:
  - `project_id` (string, required)
  - `vault_root` (string, optional)
- **Returns**: `{"status": "success", "project_id": "...", "state_summary": "...", "handoff_summary": "..."}`

---

## 2. Universal Memory Tools

### `memory_add`
Atomically records a new universal memory.
- **Parameters**:
  - `project_id` (string, required): Target project.
  - `type` (string, required): One of `knowledge`, `decision`, `hypothesis`, `observation`, `negative`, `reference`, `handoff`.
  - `title` (string, required): Concise descriptive title.
  - `content` (string, required): Markdown body content.
  - `tags` (list[string], optional): Keywords/tags.
  - `source_agent` (string, optional): Executing agent ID.
  - `source_skill` (string, optional): Calling skill name.
  - `source_ref` (string, optional): Provenance reference (DOI, run ID, commit hash, URL).
  - `related_memory_ids` (list[string], optional): Related Memory IDs.
  - `confidence` (float, optional): Subjective score (0.0 to 1.0).
  - `vault_root` (string, optional)
- **Returns**: `{"status": "success", "memory_id": "MEM-2026-0001", "file_path": "..."}`

### `memory_get`
Retrieves a memory record by ID.
- **Parameters**:
  - `project_id` (string, required)
  - `memory_id` (string, required)
  - `vault_root` (string, optional)
- **Returns**: `{"status": "success", "memory_id": "...", "title": "...", "content": "...", ...}`

### `memory_search`
Searches memories within an isolated project (or across projects if `cross_project=True`).
- **Parameters**:
  - `project_id` (string, required): Project slug or `'*'` for cross-project.
  - `query` (string, optional): Search keyword query.
  - `type` (string, optional): Filter by memory type.
  - `tags` (list[string], optional): Filter by tags.
  - `status` (string, optional): Filter by `active`, `superseded`, or `archived`.
  - `limit` (integer, default 20): Max search hits.
  - `cross_project` (boolean, default False): Whether to search all projects.
  - `vault_root` (string, optional)
- **Returns**: `{"status": "success", "total_hits": 3, "hits": [{"memory_id": "...", "title": "...", "snippet": "...", "score": 15.0, ...}]}`

### `memory_update`
Safely updates title, content, confidence, tags, or status of an existing memory in place.
- **Parameters**:
  - `project_id` (string, required)
  - `memory_id` (string, required)
  - `title` (string, optional)
  - `content` (string, optional)
  - `tags` (list[string], optional)
  - `confidence` (float, optional)
  - `status` (string, optional)
  - `related_memory_ids` (list[string], optional)
  - `vault_root` (string, optional)

### `memory_supersede`
Supersedes an old memory with a new one when new evidence overturns historical findings.
- **Parameters**:
  - `project_id` (string, required)
  - `old_memory_id` (string, required): ID of memory to supersede.
  - `title` (string, required): Title of new memory.
  - `content` (string, required): Markdown content of new memory.
  - `reason` (string, required): Rationale for revising the historical conclusion.
  - `type` (string, optional): Defaults to old memory type.
  - `tags` (list[string], optional)
  - `source_agent` (string, optional)
  - `source_skill` (string, optional)
  - `source_ref` (string, optional)
  - `confidence` (float, optional)
  - `vault_root` (string, optional)
- **Returns**: `{"status": "success", "new_memory_id": "...", "superseded_id": "..."}`

### `memory_archive`
Moves a memory file to `archive/` and sets its status to `archived`.
- **Parameters**:
  - `project_id` (string, required)
  - `memory_id` (string, required)
  - `reason` (string, optional): Archival justification.
  - `vault_root` (string, optional)

---

## 3. Context Builder Tool

### `context_build`
Constructs a token-budgeted, prioritized Markdown context pack for an agent.
- **Parameters**:
  - `project_id` (string, required)
  - `task` (string, optional): Specific task description.
  - `context_mode` (string, default "quick"): One of `quick`, `task`, `full`.
  - `max_tokens` (integer, default 4000): Maximum allowable token budget.
  - `vault_root` (string, optional)
- **Returns**: `{"status": "success", "project_id": "...", "context_pack": "..."}`

---

## 4. Handoff Tools

### `handoff_create`
Records an agent shift handoff, updating `HANDOFF.md`, syncing `STATE.md`, and saving a permanent handoff memory.
- **Parameters**:
  - `project_id` (string, required)
  - `task` (string, required)
  - `completed_work` (list[string], optional)
  - `current_progress` (string, optional)
  - `important_findings` (list[string], optional)
  - `decisions_made` (list[string], optional)
  - `issues_encountered` (list[string], optional)
  - `unresolved_items` (list[string], optional)
  - `next_steps` (list[string], optional)
  - `related_memory_ids` (list[string], optional)
  - `related_files` (list[string], optional)
  - `agent_id` (string, optional)
  - `vault_root` (string, optional)

### `handoff_get`
Retrieves the latest `HANDOFF.md` text for a project.
- **Parameters**:
  - `project_id` (string, required)
  - `vault_root` (string, optional)

---

## 5. Maintenance Tools

### `index_rebuild`
Scans all memory files in a project folder and completely regenerates `INDEX.md`.
- **Parameters**:
  - `project_id` (string, required)
  - `vault_root` (string, optional)

### `project_validate`
Validates schemas of all memories, verifies internal links, and checks project folder health.
- **Parameters**:
  - `project_id` (string, required)
  - `vault_root` (string, optional)
