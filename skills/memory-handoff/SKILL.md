---
name: memory-handoff
description: Record structured agent shift handoffs, synchronizing HANDOFF.md and STATE.md for future agents.
---

# memory-handoff Skill

Use this skill whenever wrapping up an agent session or yielding control.

## Usage Guidelines

1. **Call MCP Tool**:
   ```json
   {
     "tool": "handoff_create",
     "arguments": {
       "project_id": "my-project",
       "task": "Ablation study on attention heads",
       "completed_work": [
         "Trained baseline with 8 heads",
         "Trained variant with 16 heads",
         "Logged metrics to observations"
       ],
       "current_progress": "16-head attention shows marginal gain (0.2%) but 40% memory increase",
       "important_findings": [
         "MEM-2026-0012: 16 heads yield diminishing returns"
       ],
       "unresolved_items": [
         "Memory bottleneck on batch size 64"
       ],
       "next_steps": [
         "Test FlashAttention-2 implementation",
         "Profile memory consumption during backward pass"
       ],
       "agent_id": "claude-code"
     }
   }
   ```

2. **Retrieve Latest Handoff**:
   ```bash
   researchos handoff get my-project
   ```
