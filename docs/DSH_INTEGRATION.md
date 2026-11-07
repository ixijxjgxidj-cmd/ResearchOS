# DSH MCP Infrastructure Integration Specification

## 1. Architectural Boundary & Philosophy

ResearchOS does **NOT** build or duplicate GPU scheduling, remote SSH keychains, network relays, or machine health telemetry.
Infrastructure lifecycle management belongs entirely to **DSH** (Distributed Server Harness):
- DSH MCP Endpoint: `https://dsh-mcp-server.hulkcheng0806.workers.dev/`
- Reference Skill: `gpu-server-management` (`C:\Users\hulk cheng\.gemini\config\skills\gpu-server-management\SKILL.md`)

AI Agents simultaneously connect to **ResearchOS MCP** (for scientific memory, plans, runs, artifacts, claims) and **DSH MCP** (for GPU server discovery, leasing, execution workspace, and remote 3-tier backups).
The coordination happens in the Agent Workflow Layer (governed by `skills/experiment-execution/SKILL.md`).

---

## 2. Actual DSH MCP Tools Reference

The following tool schemas are directly extracted and verified from the official DSH MCP server specification.

### 2.1 Server Discovery: `get_servers`
- **Purpose**: Reads the current pool status, load metrics, available GPU models, active leases, and pre-cached datasets.
- **Parameters**:
  - `gpu_model` (string, optional): e.g., `"NVIDIA A100"`, `"RTX 4090"`.
  - `min_gpu_memory_gb` (number, optional): Minimum required VRAM in GB.
  - `include_offline` (boolean, optional): Include unreachable nodes (default false).
- **Return Data**:
  - Server objects with `server_id`, `name`, `host`, `port`, `username`, `connection_mode_label`, `gpu_info`, `current_task`, `current_agent`, `remaining_minutes`, `datasets` (list of `{name, path, size_gb}`), `reachable_proxies`, and `how_to_connect`.

### 2.2 Intelligent Allocation & Dataset Affinity: `plan_task_allocation`
- **Purpose**: Allocates N tasks across machines based on hardware requirements and pre-cached datasets (+100,000 score bonus for Dataset Affinity).
- **Parameters**:
  - `tasks` (array of objects, required):
    - `id` (string, required)
    - `gpu_count` (number, optional)
    - `min_gpu_memory_gb` (number, optional)
    - `min_ram_gb` (number, optional)
    - `min_disk_gb` (number, optional)
    - `min_cpu_cores` (number, optional)
    - `preferred_datasets` (array of string, optional)
- **Return Data**:
  - `recommended_allocation` table, `candidates_per_task`, `unassignable` tasks with reasons.

### 2.3 Server Claiming & Countdown: `claim_server`
- **Purpose**: Claims exclusive occupancy of a server for an experiment run, preventing multi-agent GPU contention.
- **Parameters**:
  - `server_id` (string, required): Target server ID from `get_servers`.
  - `agent` (string, required): Identity of the calling agent (e.g. `"claude-code"`, `"codex"`, `"antigravity"`).
  - `task` (string, required): Concise task summary (e.g. `"train_lora_exp_2026_001"`).
  - `duration_minutes` (number, optional): Lease countdown in minutes. Positive number sets automatic expiry timer; 0 or omitted means unlimited.
- **Return Data**: Confirmation message, lease expiration timestamp.

### 2.4 Server Release: `release_server`
- **Purpose**: Releases server occupancy after completion or failure.
- **Parameters**:
  - `server_id` (string, required): Server ID.
  - `agent` (string, optional): Agent name releasing the server.
  - `task_done` (boolean, optional): True if completed normally.
  - `note` (string, optional): Exit status or notes.

### 2.5 Dataset Management: `register_dataset` & `remove_dataset`
- **Purpose**: Registers a pre-cached dataset path on a node so future agents can leverage Dataset Affinity routing.
- **Parameters**:
  - `server_id` (string, required)
  - `name` (string, required): Dataset identifier (e.g. `"imagenet-1k"`).
  - `path` (string, required): Absolute directory path on the remote host.
  - `size_gb` (number, optional): Dataset size in GB.

### 2.6 3-Tier Intelligent Backup: `plan_server_backup`
- **Purpose**: Plans automated tiered backup of experimental outputs.
  - Tier 1: Google Drive full backup (if mounted).
  - Tier 2: Inter-server peer transfer to nodes with spare storage + index left locally.
  - Tier 3: Local core-only filtered download (irreplaceable weights/configs only).
- **Parameters**:
  - `server_id` (string, required)
  - `session_name` (string, required): e.g. `"train_lora_qwen"`
  - `summary` (string, required): e.g. `"best_checkpoint_epoch5"`
  - `remote_data_dir` (string, optional): Output directory on remote machine.
  - `has_google_drive` (boolean, optional): Whether GDrive is mounted on source host.
  - `target_peer_server_id` (string, optional): Target peer node ID.
  - `data_purpose` (string, optional): Usage purpose.
  - `data_usage_status` (string, optional): Validation metrics or status.
  - `force_local_backup` (boolean, optional): Force local download.

### 2.7 Troubleshooting Knowledge Base: `query_troubleshooting`
- **Purpose**: Queries shared collective memory of CUDA, driver, network, and framework pitfalls encountered by prior agents.
- **Parameters**:
  - `query` (string, required): Error message or symptom.
  - `server_id` (string, optional): Optional server-specific filter.

---

## 3. Run Record Data Binding in ResearchOS

When executing an experiment through DSH, ResearchOS's `Run` entity MUST record the following fields:

```yaml
schema_version: 1
id: RUN-2026-001
kind: run
project_id: PRJ-2026-001
experiment_id: EXP-2026-001
status: succeeded
agent_name: antigravity
executor_type: dsh
server_id: srv_a100_node02
server_task_id: claim_lease_94102
infrastructure_provider: dsh
working_directory: ~/workspace/train_lora_exp001_antigravity_20260815_140200
dataset_locations:
  - "/data/datasets/imagenet-1k"
environment_fingerprint:
  cuda_version: "12.4"
  driver_version: "550.54.14"
  gpu_model: "NVIDIA A100-SXM4-80GB"
  python_version: "3.11.8"
backup_reference: "gdrive://backups/20260815_train_lora/best_epoch5"
```

### Strictly Prohibited Data
The following credential types must **NEVER** be persisted in ResearchOS markdown files:
- SSH passwords or sudo passwords.
- Base64 or PEM encoded SSH private keys.
- DSH API keys, Cloudflare Worker tokens, or Bearer headers.
All connections must be negotiated live through DSH MCP by the executing agent.

---

## 4. Verification & Testing Status

| Capability | Real DSH Status | ResearchOS Test Mechanism |
|---|---|---|
| Server Discovery (`get_servers`) | External Live Worker | Mock DSH Adapter (`test_mock_dsh.py`) |
| Server Claim & Lease (`claim_server`) | External Live Worker | Mock DSH Adapter (`test_mock_dsh.py`) |
| Workspace Isolation (`mkdir ~/workspace/...`) | Remote SSH execution | Verified via Agent Workflow Protocol |
| 3-Tier Backup (`plan_server_backup`) | External Live Worker | Mock DSH Adapter (`test_mock_dsh.py`) |
| Server Release (`release_server`) | External Live Worker | Mock DSH Adapter (`test_mock_dsh.py`) |
| Dataset Affinity (`plan_task_allocation`) | External Live Worker | Mock DSH Adapter (`test_mock_dsh.py`) |

> [!NOTE]
> When executing in an environment without internet access to `https://dsh-mcp-server.hulkcheng0806.workers.dev/`, the `MockDSHAdapter` (`src/researchos/integration/dsh/mock_adapter.py`) provides deterministic simulation of server claiming, allocation, and backup planning without faking real infrastructure status.
