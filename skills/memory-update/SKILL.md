---
name: memory-update
description: Update existing memories or supersede historical conclusions with newly verified scientific evidence.
---

# memory-update Skill

Use this skill when refining an existing memory in-place or superseding an older hypothesis/observation when new conflicting evidence arrives.

## Usage Guidelines

1. **In-place Update (Minor refinement, tag addition, confidence adjustment)**:
   ```json
   {
     "tool": "memory_update",
     "arguments": {
       "project_id": "my-project",
       "memory_id": "MEM-2026-0005",
       "confidence": 0.98,
       "tags": ["verified", "production"]
     }
   }
   ```

2. **Supersede Memory (When new findings overturn previous conclusions)**:
   ```json
   {
     "tool": "memory_supersede",
     "arguments": {
       "project_id": "my-project",
       "old_memory_id": "MEM-2026-0005",
       "title": "Batch size 512 causes divergence on larger datasets",
       "content": "New evaluation demonstrates that scaling beyond 10M samples causes catastrophic gradient explosion with batch size 512.",
       "reason": "Evaluated on expanded benchmark dataset (run-108). Previous observation was limited to small toy dataset.",
       "type": "observation",
       "source_ref": "RUN-108"
     }
   }
   ```
