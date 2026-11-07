---
name: experiment-execution
description: Standard operating procedure for executing an experiment run, logging telemetry, and integrating with DSH infrastructure.
---

# Experiment Execution Skill

## Purpose
Governs the physical or remote execution of an experimental run, ensuring strict separation between planned parameters and actual runtime parameters, isolated run workspaces, code versioning, and artifact registration.

## Step-by-Step Procedure

1. **Verify Experiment Readiness**:
   - Ensure target Experiment is in status `ready` or `planned`.
   - Call `research_experiment_get(experiment_id)`.

2. **Initialize Run Record**:
   - Call `research_run_create`:
     - `experiment_id`: Target experiment.
     - `agent_name`: Name or model identifier of the executing agent.
     - `executor_type`: `"local"` or `"dsh"`.
     - `code_repository`: Git repository path or remote URL.
     - `code_commit`: Current Git commit hash.

3. **Workspace Isolation**:
   - **Local Run**: Create an isolated run folder, e.g., `./runs/{RUN-ID}/`.
   - **DSH Remote Run**:
     - Call DSH MCP `get_servers` to inspect GPU availability.
     - Optionally invoke `plan_task_allocation` to match dataset affinity.
     - Claim server via `claim_server(server_id, agent, task, duration_minutes)`.
     - Create dedicated remote workspace: `~/workspace/{session}_{agent}_{time}`.
     - Record `server_id` and `working_directory` in the Run record via `research_run_update`.

4. **Execute & Record Actual Telemetry**:
   - Run the script or training command.
   - Capture:
     - Real command-line arguments and actual parameters used (e.g. learning rate, batch size, random seed).
     - Standard output / error logs.
     - Output checkpoint and metric files.

5. **Register Output Artifacts**:
   - For every key output file (logs, checkpoints, confusion matrices, loss curves), call:
     `research_artifact_register(run_id, path, role="figure"|"metrics"|"checkpoint"|"log")`.
   - ResearchOS will compute SHA-256 hashes and register immutable metadata.

6. **Post-Execution Cleanup (If using DSH)**:
   - Call DSH MCP `plan_server_backup` to save weights / checkpoints.
   - Call DSH MCP `release_server` to release the server lease for other agents.
   - Record backup reference in the Run record.
