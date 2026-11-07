---
name: experiment-execution
description: Standard operating procedure for executing an experiment run, logging telemetry, and referencing the gpu-server-management skill for GPU server claiming and backups.
---

# Experiment Execution Skill

## Purpose
Governs the physical or remote execution of an experimental run, ensuring strict separation between planned parameters and actual runtime parameters, isolated run workspaces, code versioning, and artifact registration.

> [!IMPORTANT]
> **Zero Infrastructure Duplication Principle**:
> ResearchOS does NOT implement or duplicate server discovery, claiming, GPU scheduling, or backup tools.
> For all remote GPU infrastructure operations, this skill **directly references and delegates to the user's existing `gpu-server-management` skill**.
> ResearchOS manages the scientific chain of custody; `gpu-server-management` (via DSH MCP) manages the physical/cloud compute nodes.

---

## Step-by-Step Procedure

### 1. Remote GPU Compute & Infrastructure Lifecycle (Skill: `gpu-server-management`)
If the experiment requires remote GPU compute (e.g. training, fine-tuning, heavy inference):
**The Agent MUST activate and follow the standard 5-step lifecycle in the `gpu-server-management` skill**:

1. **Read the pool (`get_servers`)**:
   Check online status, free VRAM, `current_task` (busy check), and cached datasets. Optionally call `plan_task_allocation` to utilize **Dataset Affinity** (+100,000 score boost).
2. **Claim with optional Countdown (`claim_server`)**:
   ```yaml
   claim_server:
     server_id: "<target-server-id>"
     agent: "<your-agent-identifier>"       # e.g., "claude-code", "antigravity"
     task: "<task-summary-and-exp-id>"     # e.g., "EXP-2026-001 lora training"
     duration_minutes: 120                  # Countdown lease timer
   ```
3. **Workspace Isolation (Mandatory DSH Protocol)**:
   Strictly create the dedicated isolated workspace before executing any code:
   ```bash
   mkdir -p ~/workspace/{session_name}_{agent_name}_{YYYYMMDD_HHMMSS}
   cd ~/workspace/{session_name}_{agent_name}_{YYYYMMDD_HHMMSS}
   ```
   All code clones, environments, scripts, checkpoints, and intermediate logs must reside strictly inside this workspace.

---

### 2. Initialize ResearchOS Run Record
Simultaneously bind the compute lease to the scientific record by calling ResearchOS MCP `research_run_create`:
- `experiment_id`: Target experiment ID (e.g. `EXP-2026-001`).
- `agent_name`: Name or model identifier of the executing agent.
- `executor_type`: `"dsh"` (for remote GPU runs) or `"local"`.
- `server_id`: The `server_id` claimed via `gpu-server-management`.
- `server_task_id`: The task lease description used in `claim_server`.
- `working_directory`: The isolated `~/workspace/...` path created above.
- `code_repository`: Git repository path or remote URL.
- `code_commit`: Current Git commit hash (`git rev-parse HEAD`).

---

### 3. Execute & Record Actual Telemetry
- Run the script or training command inside the isolated remote workspace.
- Record the **actual parameters** (e.g. real learning rate, actual batch size, random seed) — never assume they match the plan without verifying.
- Capture execution logs, metrics (e.g. loss curves, validation accuracy), and telemetry.

---

### 4. Register Output Artifacts
- For every key output file (model weights, figures, confusion matrices, evaluation logs), call ResearchOS MCP:
  `research_artifact_register(run_id=..., path=..., role="checkpoint"|"metrics"|"figure"|"log")`.
- ResearchOS computes the cryptographic SHA-256 hash and records immutable metadata.

---

### 5. Post-Execution 3-Tier Backup & Server Release (Skill: `gpu-server-management`)
When execution finishes (or encounters an error):
1. **Tiered Backup (`plan_server_backup`)**:
   Follow the 3-tier backup hierarchy defined in `gpu-server-management`:
   - Tier 1: Google Drive full backup (if mounted).
   - Tier 2: Inter-server peer transfer to nodes with spare storage + index left locally.
   - Tier 3: Local core-only filtered download (irreplaceable weights/configs only).
   Record the resulting `backup_reference` into the ResearchOS Run record.
2. **Release Server (`release_server`)**:
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
   - `actual_parameters`: Verified runtime parameters.
   - `metrics`: Final evaluation metrics.
   - `result_summary`: Markdown summary of empirical outcomes.
