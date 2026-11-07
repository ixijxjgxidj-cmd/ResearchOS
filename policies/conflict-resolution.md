# Conflict Resolution & Revision Policy

In long-running scientific research, facts and conclusions evolve as new data is gathered.

## 1. Superseding vs. Overwriting
- Never overwrite or silently delete historical memories that represent earlier observations or hypotheses.
- When new evidence disproves or refines an existing memory:
  1. Keep the original memory record intact.
  2. Transition its status to `superseded`.
  3. Create a new memory record with `supersedes: <old_memory_id>`.
  4. Clearly document in the new memory body why the previous conclusion was revised and cite the new evidence.

## 2. Multi-Agent Concurrent Writes
- All writes to `INDEX.md`, `STATE.md`, `PROJECT.md`, and individual memory files use filesystem locking (`portalocker`) and atomic temp-file replacement.
- In case of competing claims between agents, record both as hypotheses or observations with respective `confidence` scores and `source_ref` pointers until settled by subsequent validation.
