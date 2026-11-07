---
name: experiment-execution
description: Standard operating procedure for executing an experiment run, logging telemetry, and directly reusing DSH MCP for GPU server claiming and backups.
---

# Experiment Execution Skill

## Purpose
Governs the execution of experimental runs with strict separation between planned parameters and actual runtime parameters, isolated run workspaces, code versioning, and artifact registration.

> [!IMPORTANT]
> **Zero Infrastructure Duplication Principle**:
> ResearchOS does NOT implement or duplicate server discovery, claiming, GPU scheduling, or backup tools.
> All infrastructure management strictly reuses the user's existing **DSH MCP (`dsh-mcp-server`)** and the **`gpu-server-management`** skill.
> ResearchOS manages the scientific chain of custody; DSH manages the physical/cloud compute nodes.

---

## Step-by-Step Procedure

### 1. Pre-execution & Server Claiming (DSH MCP)
If the experiment requires remote GPU compute:
1. **Discover Available GPUs**:
   Call DSH MCP `get_servers(gpu_model=..., min_gpu_memory_gb=...)` to check pool status, VRAM, and pre-cached datasets.
   Or call `plan_task_allocation` to utilize **Dataset Affinity** (+100,000 score bonus).
2. **Claim Server via DSH MCP**:
   Call `claim_server`:
   ```yaml
   claim_server:
     server_id: "<target-server-id>"
     agent: "<your-agent-identifier>"       # e.g., "claude-code", "antigravity"
     task: "<task-summary-and-exp-id>"     # e.g., "EXP-2026-001 lora training"
     duration_minutes: 120                  # Optional countdown lease timer
   ```
   *Note: Never fabricate custom server-management tools. Always call `dsh-mcp-server` directly.*

---

### 2. Initialize ResearchOS Run Record
Call ResearchOS MCP `research_run_create`:
- `experiment_id`: Target experiment ID (e.g. `EXP-2026-001`).
- `agent_name`: Name or model identifier of the executing agent.
- `executor_type`: `"dsh"` (for remote GPU runs) or `"local"`.
- `server_id`: The DSH `server_id` obtained from `get_servers` / `claim_server`.
- `server_task_id`: The lease or task description used in `claim_server`.
- `code_repository`: Git repository path or remote URL.
- `code_commit`: Current Git commit hash (`git rev-parse HEAD`).

---

### 3. Remote Workspace Isolation (Mandatory DSH Protocol)
- **SSH into Claimed Server**: Connect using the SSH parameters from DSH `get_servers`.
- **Create Dedicated Isolated Workspace**:
  ```bash
  mkdir -p ~/workspace/{session_name}_{agent_name}_{YYYYMMDD_HHMMSS}
  cd ~/workspace/{session_name}_{agent_name}_{YYYYMMDD_HHMMSS}
  ```
- **Strict Isolation Rule**: All code clones, virtual environments, execution scripts, checkpoints, and intermediate logs must reside strictly inside this workspace.
- Record `working_directory` in the Run record via `research_run_update`.

---

### 4. Execute & Record Actual Telemetry
- Run the experiment / training process.
- Record the **actual parameters** (e.g. real learning rate, actual batch size, random seed) — never assume they match the plan without verifying.
- Capture execution logs, metrics (e.g. loss curves, validation accuracy), and telemetry.

---

### 5. Register Output Artifacts
- For every key output file (model weights, figures, confusion matrices, evaluation logs), call ResearchOS MCP:
  `research_artifact_register(run_id=..., path=..., role="checkpoint"|"metrics"|"figure"|"log")`.
- ResearchOS computes the cryptographic SHA-256 hash and records immutable metadata.

---

### 6. Post-Execution 3-Tier Backup & Server Release (DSH MCP)
When execution completes (or fails):
1. **Tiered Backup via DSH MCP**:
   Call DSH MCP `plan_server_backup`:
   ```yaml
   plan_server_backup:
     server_id: "<server-id>"
     session_name: "<session-name>"
     summary: "<checkpoint-summary>"
     remote_data_dir: "~/workspace/.../output"
     has_google_drive: true/false
   ```
   Record the resulting `backup_reference` in the ResearchOS Run record.
2. **Release Server via DSH MCP**:
   Call DSH MCP `release_server`:
   ```yaml
   release_server:
     server_id: "<server-id>"
     agent: "<your-agent-identifier>"
     task_done: true
     note: "EXP-2026-001 finished. Artifacts registered in ResearchOS."
   ```
3. **Finalize Run Record**:
   Call ResearchOS MCP `research_run_complete`:
   - `status`: `"succeeded"`, `"failed"`, or `"interrupted"`.
   - `actual_parameters`: Verified parameters.
   - `metrics`: Final evaluation metrics.
   - `result_summary`: Markdown summary of empirical outcomes.
