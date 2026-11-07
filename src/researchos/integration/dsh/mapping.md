# ResearchOS <-> DSH Field & Tool Mapping

| ResearchOS Concept | Corresponding DSH Tool / Field | Notes |
|---|---|---|
| `Run.executor_type` | `"dsh"` | Explicitly distinguishes DSH compute from local machine runs |
| `Run.server_id` | `claim_server.server_id` / `get_servers.server_id` | Unique ID of remote compute node |
| `Run.server_task_id` | Lease identifier returned by `claim_server` | Tracks concurrency lock on remote GPU |
| `Run.working_directory` | `~/workspace/{session}_{agent}_{timestamp}` | Enforces workspace isolation |
| `Run.dataset_locations` | `register_dataset.path` / `get_servers.datasets` | Pre-cached paths for Dataset Affinity |
| `Run.environment_fingerprint` | `get_servers.gpu_info`, live CUDA version | Hardware and framework snapshot |
| `Run.backup_reference` | Output of `plan_server_backup` | Identifies Google Drive / peer node sync index |
| `Artifact.storage_backend` | `"dsh"` or `"gdrive"` | For large artifacts stored off-vault |
