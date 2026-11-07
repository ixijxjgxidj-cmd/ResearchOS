---
name: memory-context
description: Build prioritized, token-budgeted context packs for agent initialization or task execution.
---

# memory-context Skill

Use this skill immediately upon entering a project or before starting a specific sub-task.

## Usage Guidelines

1. **Context Modes**:
   - `quick`: Best for first entry. Returns `PROJECT.md`, `STATE.md`, latest `HANDOFF.md`, and recent key decisions.
   - `task`: Focused on a specific objective. Matches relevant knowledge, observations, and negative lessons to the task description.
   - `full`: Complete overview across all memories while staying within the token budget.

2. **Call MCP Tool**:
   ```json
   {
     "tool": "context_build",
     "arguments": {
       "project_id": "my-project",
       "task": "Optimize inference latency on edge devices",
       "context_mode": "task",
       "max_tokens": 4000
     }
   }
   ```

3. **Or CLI Command**:
   ```bash
   researchos context build my-project --task "inference latency" --mode task --max-tokens 4000
   ```
