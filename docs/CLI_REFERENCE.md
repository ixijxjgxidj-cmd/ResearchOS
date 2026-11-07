# ResearchOS CLI Reference Manual

The `research` command provides an ergonomic terminal interface for human researchers and script-based AI agents.

## Global Options
- `--vault, -v PATH`: Specify custom ResearchVault root directory.
- `RESEARCH_VAULT_ROOT`: Environment variable fallback.
- `--json`: Output machine-readable JSON across commands.

---

## Commands

```bash
# Vault Initialization
research init [--vault PATH]

# Project Commands
research project create "Project Name" [--question "Question"] [--objective "Obj 1"]
research project list
research project show PRJ-2026-001

# Experiment Commands
research experiment create PRJ-2026-001 "Experiment Title" [--hypothesis "Hyp"] [--method "Method"] [--params '{"lr": 0.001}'] [--exploratory]
research experiment list [--project PRJ-2026-001]
research experiment pending [--project PRJ-2026-001]
research experiment show EXP-2026-001
research experiment validate EXP-2026-001

# Run Commands
research run create EXP-2026-001 [--agent "claude-code"] [--executor "local"]
research run show RUN-2026-001
research run complete RUN-2026-001 --actual-params '{"lr": 0.002, "batch_size": 32}' --status succeeded --outcome positive [--metrics '{"acc": 0.94}'] [--summary "Converged"]

# Literature Commands
research paper create "Paper Title" --citekey "author2026key" [--author "Author A"] [--year 2026] [--abstract "Summary"]
research paper search "diffusion models"

# Artifact Commands
research artifact register RUN-2026-001 /path/to/checkpoint.pt --role checkpoint [--name "best_model.pt"]

# Context Builder
research context build EXP-2026-001

# Handoff
research handoff update PRJ-2026-001 --focus "Completing baseline evaluations" --completed "Ran EXP-001" --next "Run ablation on EXP-002"

# Research Audit
research audit [--project PRJ-2026-001]
```
