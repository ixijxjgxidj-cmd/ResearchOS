# ResearchOS Universal Memory Data Model (v2)

This document specifies the authoritative data models, frontmatter schemas, and directory layouts for ResearchOS.

---

## 1. Universal Memory Model

ResearchOS discards complex, domain-specific research management models (Experiments, Runs, Findings, Claims) in favor of a single unified entity: **Universal Memory**.

### 1.1 Memory Types

| Memory Type | Directory | Description |
| :--- | :--- | :--- |
| `knowledge` | `knowledge/` | Distilled facts, principles, validated methods, formulas |
| `decision` | `decisions/` | Architectural or scientific choices with explicit rationale |
| `hypothesis` | `hypotheses/` | Testable assumptions, expected outcomes, verification status |
| `observation` | `observations/` | Empirical results, benchmark metrics, experimental findings |
| `negative` | `negative/` | Validated failed approaches, unviable parameters, negative outcomes, pitfalls |
| `reference` | `references/` | Pointers to external papers (DOIs), dataset paths, git commits, artifacts |
| `handoff` | `handoffs/` | Inter-agent shift handoff notes |

### 1.2 Memory Frontmatter Schema

Every memory markdown file (`MEM-YYYY-NNNN.md`) starts with standard YAML frontmatter:

```yaml
---
id: MEM-2026-0001
project_id: deep-residual-scaling
type: observation
title: Optimal Depth-to-Width Ratio on 7B Frontier is 1:3.2
created_at: 2026-11-08T00:00:00+08:00
updated_at: 2026-11-08T00:00:00+08:00
status: active # active, superseded, archived
source_agent: codex
source_skill: experiment-skill
source_ref: RUN-042
confidence: 0.94 # float between 0.0 and 1.0 (or null)
tags:
  - scaling-laws
  - frontier
related:
  - MEM-2026-0002
supersedes: null # or MEM-YYYY-NNNN
---

# Optimal Depth-to-Width Ratio on 7B Frontier is 1:3.2

Markdown body containing detailed evidence, observations, and formulas...
```

---

## 2. Project Files

Each project folder (`ResearchVault/<project_id>/`) contains four root status documents:

### 2.1 `PROJECT.md`
Stores project identity, long-term goals, and scope:
```yaml
---
project_id: deep-residual-scaling
project_name: Deep Residual Scaling Laws
description: Empirical investigation of transformer depth vs width tradeoffs
research_goal: Find optimal Chinchilla-style aspect ratio for 7B parameters
created_at: 2026-11-08T00:00:00+08:00
updated_at: 2026-11-08T00:00:00+08:00
status: active
tags:
  - scaling
  - transformers
---
```

### 2.2 `STATE.md`
Tracks dynamic research progress, current facts, and active blockers:
- `## 1. 当前研究目标 (Current Goal)`
- `## 2. 当前已知事实 (Known Facts)`
- `## 3. 当前研究进展 (Current Progress)`
- `## 4. 当前重要问题 (Key Questions)`
- `## 5. 尚未解决的问题 (Unresolved Issues)`
- `## 6. 最近的重要变化 (Recent Changes)`
- `## 7. 下一步关注事项 (Next Focus)`

### 2.3 `INDEX.md`
Derived Markdown catalog rebuilt by scanning project files:
- Total memory counts by type
- Catalog table with relative links `[title](relative_path)`
- Superseded and archived memory references

### 2.4 `HANDOFF.md`
Captures the latest agent shift handoff summary. Historical handoffs are archived in `handoffs/MEM-*.md`.
