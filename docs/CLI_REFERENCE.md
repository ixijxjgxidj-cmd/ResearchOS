# ResearchOS CLI Reference

ResearchOS provides a unified command line interface for researchers and scripts.

Command aliases: `researchos` or `research`.

---

## 1. Project Commands (`researchos project`)

### `researchos project create`
Idempotently creates a new independent project folder with standard subdirectories and documents.
```bash
researchos project create "My Research Study" --id my-study --goal "Study Transformer Attention" --desc "Ablation study" --json
```

### `researchos project list`
Lists all research projects in the vault.
```bash
researchos project list [--vault <path>] [--json]
```

### `researchos project get`
Displays project details, state, and file path.
```bash
researchos project get my-study [--json]
```

### `researchos project rebuild-index`
Scans all memory files in the project and fully regenerates `INDEX.md`.
```bash
researchos project rebuild-index my-study
```

### `researchos project validate`
Validates schemas and links across all project memories.
```bash
researchos project validate my-study
```

---

## 2. Memory Commands (`researchos memory`)

### `researchos memory add`
Records a new universal memory.
```bash
researchos memory add my-study \
  --type observation \
  --title "FlashAttention-2 reduces memory footprint by 50%" \
  --content "Empirical evaluation on A100 confirms 2x memory reduction and 1.8x speedup." \
  --tag performance \
  --tag attention \
  --agent codex \
  --ref RUN-088 \
  --confidence 0.98
```

### `researchos memory get`
Reads a memory record by ID.
```bash
researchos memory get my-study MEM-2026-0001 [--json]
```

### `researchos memory search`
Searches memories within a project (or across projects).
```bash
researchos memory search my-study --query "FlashAttention" --type observation --limit 10
# Or cross-project search:
researchos memory search "*" --query "transformer" --cross-project
```

### `researchos memory update`
Safely updates title, content, confidence, or status in place.
```bash
researchos memory update my-study MEM-2026-0001 --confidence 0.99
```

### `researchos memory supersede`
Supersedes an older memory with a revised memory, recording the reason.
```bash
researchos memory supersede my-study MEM-2026-0001 \
  --title "FlashAttention-3 Delivers FP8 Speedups" \
  --content "New FP8 tensor core integration yields 1.5x additional speedup over FlashAttention-2." \
  --reason "Upgraded to Hopper H100 architecture benchmarks."
```

### `researchos memory archive`
Moves a memory to `archive/` and marks its status as `archived`.
```bash
researchos memory archive my-study MEM-2026-0001 --reason "Superseded by generation 3"
```

---

## 3. Context Builder Commands (`researchos context`)

### `researchos context build`
Builds a prioritized, token-budgeted agent context pack.
```bash
researchos context build my-study --mode task --task "Optimize memory consumption" --max-tokens 4000
```

---

## 4. Handoff Commands (`researchos handoff`)

### `researchos handoff create`
Records an agent shift handoff, updating `HANDOFF.md` and syncing `STATE.md`.
```bash
researchos handoff create my-study \
  --task "Attention optimization" \
  --completed "Evaluated FlashAttention-2" \
  --progress "Memory reduced by 50%" \
  --finding "Optimal chunk size is 128" \
  --next "Test FlashAttention-3" \
  --agent codex
```

### `researchos handoff get`
Displays the latest `HANDOFF.md` content.
```bash
researchos handoff get my-study
```
