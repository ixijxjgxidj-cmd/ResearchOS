---
name: memory-retrieve
description: Search and retrieve persistent research memories by keyword, tags, type, or date range within an isolated project.
---

# memory-retrieve Skill

Use this skill when you need to query past observations, decisions, negative lessons, or literature references stored in the project.

## Usage Guidelines

1. **Call MCP Tool**:
   ```json
   {
     "tool": "memory_search",
     "arguments": {
       "project_id": "my-project",
       "query": "learning rate warmup",
       "type": "negative",
       "tags": ["hyperparameters"],
       "limit": 10
     }
   }
   ```

2. **Or CLI Command**:
   ```bash
   researchos memory search my-project --query "learning rate" --type negative
   ```

3. **Get Exact Memory**:
   ```bash
   researchos memory get my-project MEM-2026-0001
   ```
