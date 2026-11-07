"""Mock DSH adapter for testing multi-agent GPU workflows without live cluster connectivity."""

from datetime import datetime, timezone
from typing import Any


class MockDSHAdapter:
    """Simulates DSH MCP server tool responses for offline development and CI testing."""

    def __init__(self) -> None:
        self.servers: dict[str, dict[str, Any]] = {
            "srv_a100_01": {
                "server_id": "srv_a100_01",
                "name": "lambda-a100-primary",
                "host": "192.168.1.101",
                "gpu_model": "NVIDIA A100-SXM4-80GB",
                "gpu_count": 8,
                "free_gpu_memory_gb": 80,
                "current_task": None,
                "current_agent": None,
                "datasets": [{"name": "cifar-10", "path": "/data/cifar10", "size_gb": 2.5}],
            },
            "srv_4090_01": {
                "server_id": "srv_4090_01",
                "name": "lab-rtx4090-worker",
                "host": "192.168.1.102",
                "gpu_model": "NVIDIA GeForce RTX 4090",
                "gpu_count": 2,
                "free_gpu_memory_gb": 24,
                "current_task": None,
                "current_agent": None,
                "datasets": [],
            },
        }
        self.leases: dict[str, dict[str, Any]] = {}
        self.backups: list[dict[str, Any]] = []

    def get_servers(
        self,
        gpu_model: str | None = None,
        min_gpu_memory_gb: float | None = None,
        include_offline: bool = False,
    ) -> list[dict[str, Any]]:
        results = []
        for s in self.servers.values():
            if gpu_model and gpu_model.lower() not in s["gpu_model"].lower():
                continue
            if min_gpu_memory_gb and s["free_gpu_memory_gb"] < min_gpu_memory_gb:
                continue
            results.append(s)
        return results

    def claim_server(
        self,
        server_id: str,
        agent: str,
        task: str,
        duration_minutes: float = 60,
    ) -> dict[str, Any]:
        if server_id not in self.servers:
            raise ValueError(f"Server {server_id} not found.")

        srv = self.servers[server_id]
        if srv["current_task"] and srv["current_agent"] != agent:
            raise RuntimeError(f"Server {server_id} is already occupied by agent '{srv['current_agent']}' on task '{srv['current_task']}'.")

        srv["current_task"] = task
        srv["current_agent"] = agent
        lease_id = f"mock_lease_{server_id}_{int(datetime.now(timezone.utc).timestamp())}"
        self.leases[server_id] = {
            "lease_id": lease_id,
            "agent": agent,
            "task": task,
            "duration_minutes": duration_minutes,
        }
        return {
            "status": "claimed",
            "server_id": server_id,
            "lease_id": lease_id,
            "agent": agent,
            "task": task,
            "expires_in_minutes": duration_minutes,
        }

    def release_server(
        self,
        server_id: str,
        agent: str | None = None,
        task_done: bool = True,
        note: str | None = None,
    ) -> dict[str, Any]:
        if server_id not in self.servers:
            raise ValueError(f"Server {server_id} not found.")

        srv = self.servers[server_id]
        srv["current_task"] = None
        srv["current_agent"] = None
        self.leases.pop(server_id, None)

        return {
            "status": "released",
            "server_id": server_id,
            "task_done": task_done,
            "note": note or "Task finished.",
        }

    def plan_server_backup(
        self,
        server_id: str,
        session_name: str,
        summary: str,
        has_google_drive: bool = False,
        remote_data_dir: str | None = None,
        data_purpose: str | None = None,
        data_usage_status: str | None = None,
    ) -> dict[str, Any]:
        backup_ref = f"mock_backup://{server_id}/{session_name}/{summary}"
        record = {
            "backup_ref": backup_ref,
            "server_id": server_id,
            "session_name": session_name,
            "summary": summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.backups.append(record)
        return {
            "status": "planned",
            "backup_reference": backup_ref,
            "route": "gdrive" if has_google_drive else "peer_server",
            "details": record,
        }

    def register_dataset(self, server_id: str, name: str, path: str, size_gb: float = 0.0) -> dict[str, Any]:
        if server_id not in self.servers:
            raise ValueError(f"Server {server_id} not found.")
        self.servers[server_id]["datasets"].append({"name": name, "path": path, "size_gb": size_gb})
        return {"status": "registered", "dataset": name, "server_id": server_id}
