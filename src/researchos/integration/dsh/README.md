# DSH Integration Module

This module documents the interface contracts between ResearchOS and the DSH (Distributed Server Harness) MCP infrastructure.

## Separation of Concerns
- **ResearchOS**: Governs scientific hypotheses, experimental plans, immutable runs, artifacts, findings, claims, and context packs.
- **DSH**: Governs physical and cloud GPU hosts, SSH access, hardware telemetry, server leases, and multi-tier backups.

Neither system supersedes the other; AI Agents coordinate both via standard MCP tool calls.
