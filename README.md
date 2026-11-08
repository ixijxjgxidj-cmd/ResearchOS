---
title: ResearchOS MCP
emoji: 🔬
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# ResearchOS

**A Lightweight, Cross-Agent, Cross-Session Scientific Memory Architecture with Context Compaction Auto-Recovery**

ResearchOS 是一个专为 AI 科研 Agent 设计的轻量级长期科研记忆系统。它具有 **Agent-independent、Filesystem-first、Project-isolated、Auto-Recovery** 的核心特征。

本次升级的核心目标：
**让 Agent 在每次上下文压缩（Context Compaction）、会话重启（Session Reboot）或 Agent 切换后，都能自动恢复当前科研项目的关键记忆，而不需要重新阅读海量历史对话或实验文件。**

---

## 1. 核心设计原则 (Core Principles)

1. **Memory First**: ResearchOS 专注于保存长期记忆、当前工作状态、核心决策、实验观察与失败经验。不承担 GPU 调度、代码运行、数据集下载或论文自动生成等具体工作流。
2. **Filesystem First**: 本地 Markdown 文件是唯一权威载体，直接可读可编辑，不绑定特定厂商、私有数据库或 Obsidian 专有插件。
3. **Project Isolation**: 每个项目拥有独立的物理目录 (`ResearchVault/<project_id>/`)，严禁跨项目记忆污染。
4. **Deterministic Project Resolution (Zero Guessing)**: 通过优先级（显式参数 > 环境变量 > 向上目录树查找）精确匹配项目边界，坚决杜绝随意猜测。
5. **Token Budget Awareness**: 核心恢复文件 `MEMORY.md` 严格控制在 400–800 tokens（硬上限 1,200 tokens）。
6. **Multi-Agent Safe**: 细粒度文件锁与原子文件替换保证多 Agent 并发写入无竞争、无损坏。

---

## 2. 目录结构与权威职责

```text
ResearchVault/
└── my-research-project/
    ├── PROJECT.md          # 权威文件：稳定的项目定义与研究约束
    ├── STATE.md            # 权威文件：当前研究状态与下一步任务
    ├── HANDOFF.md          # 权威文件：最新一次 Agent 交接摘要
    ├── INDEX.md            # 索引目录：全部详细记忆的可重建索引
    ├── MEMORY.md           # 自动生成的轻量上下文恢复快照 (~400-800 tokens)
    │
    ├── records/            # 统一存储详细科研记录 (亦支持 legacy 分类子目录)
    │   ├── DEC-0001_vit_patch16.md
    │   ├── OBS-0001_snr_baseline.md
    │   ├── NEG-0001_mask_ratio_collapse.md
    │   ├── HYP-0001_fourier_attention.md
    │   └── REF-0001_mae_paper.md
    ├── handoffs/           # 历史交接备忘录
    └── .researchos/        # 事务锁、版本控制与自动备份
```

---

## 3. MEMORY.md — 核心上下文恢复快照

`MEMORY.md` 是由底层权威文件自动合成的轻量上下文快照，统一包含 4 大标准章节：

```markdown
---
schema_version: 1
project_id: jepa-seismic
generated_at: 2026-11-08T16:00:00+08:00
memory_version: 12
---

# MEMORY

## 1. STABLE MEMORY

### Project Identity
- Project: Latent Masking Seismic
- Research Goal: Unsupervised pretraining on seismic traces
- Core Research Question: Can latent masking improve SNR?
- Project Root: ResearchVault/jepa-seismic

### Fixed Constraints
- Max GPU Memory: 80GB (Single A100)
- Sequence Length: 4096 tokens

### Key Decisions
- DEC-0001: Select ViT-Patch16 Architecture due to linear scaling

## 2. WORKING MEMORY

### Current Stage
- Stage 2: Architecture Search & Baseline Evaluation

### Current Task
- Evaluating patch size 16 vs 32 on synthetic test set

### Last Completed Work
- Completed baseline data loader verification
- Exported initial checkpoint weights

### Next Actions
1. Run ablation on patch size 16 vs 32
2. Plot latent loss curves across 50 epochs

### Current Blockers
- Pending A100 GPU cluster availability

### Open Questions
- Does 2D Fourier phase embedding reduce spatial ringing?

## 3. CRITICAL WARNINGS

- [WARNING] NEG-0001: Mask ratio above 0.85 leads to latent representation collapse.

## 4. MEMORY POINTERS

- Project Definition: PROJECT.md
- Detailed State: STATE.md
- Latest Handoff: HANDOFF.md
- Memory Index: INDEX.md
- Detailed Records: records/
- Key Observations: `OBS-0001`
- Key Decisions: `DEC-0001`
- Key Pitfalls: `NEG-0001`
```

---

## 4. Context Compaction Hook — 自动记忆恢复核心

针对长上下文或多轮对话导致的主动/被动压缩（Context Compaction），ResearchOS 提供了独立于 Agent 平台的 Lifecycle Hook Core：

```mermaid
flowchart LR
    A["Event A: Session Start"] --> B["Event B: Pre-Compaction\n(Save State & Handoff)"]
    B --> C["Context Compaction\n(Host LLM Truncation)"]
    C --> D["Event C: Post-Compaction\n(Inject Restored MEMORY.md)"]
    D --> E["Agent Resumes with Full Context"]
    E --> F["Event D: Session End\n(Create Handoff)"]
```

- **Event A (Session Start)**: 自动定位项目，校验 `MEMORY.md`，注入初始上下文。
- **Event B (Pre-Compaction)**: 压缩前自动保存当前阶段、已完成工作和下一步任务至 `STATE.md` 与 `HANDOFF.md`。
- **Event C (Post-Compaction — CORE)**: 压缩完成后立即触发，自动将最新 4-section `MEMORY.md` 注入 Agent 上下文（通过 Claude Code `additionalContext` 或 Antigravity 提示词注入），实现**无感记忆恢复**。
- **Event D (Session End)**: 会话结束或交接时生成交接记录。

详细配置指南请参考 [docs/hooks.md](docs/hooks.md) 与 [docs/hook_compatibility_matrix.md](docs/hook_compatibility_matrix.md)。

---

## 5. 三层渐进式检索 (Three-Level Retrieval)

ResearchOS 提供灵活的三层检索机制，避免一次性向 Context 倾倒海量数据：

1. **L0 (Quick 模式)**: 仅读取 `MEMORY.md` (~400–800 tokens)，用于快速恢复项目意识。
2. **L1 (Task 模式)**: 读取 `MEMORY.md` + `PROJECT.md` + `STATE.md` + `HANDOFF.md` + BM25 检索的高度相关记忆记录。
3. **L2 (Paper 模式)**: 提取结构化实验证据表（Run ID、指标摘要、完成/失败/中断状态），假设类记忆自动标注 `[Hypothesis - Unverified Claim]`。支持按 `paper_section` 过滤。
4. **Full 模式**: 完整拉取所有活跃记忆与历史记录。

---

## 6. MCP Server 双 Profile 模式

通过 `--profile` 参数或环境变量 `RESEARCHOS_PROFILE=lite|advanced` 切换：

### Lite Profile (默认模式 — 极简 6 工具)
保持 Agent 工具列表清爽，降低上下文认知负担：
1. `project_get`: 读取项目元数据与最新状态。
2. `context_build`: 构建指定模式 (`quick`, `task`, `paper`, `full`) 的上下文包。
3. `memory_add`: 持久化科研记忆 (`DEC`, `OBS`, `NEG`, `HYP`, `REF`, `KNO`)。
4. `memory_search`: 隔离检索当前项目的记忆记录。
5. `memory_get`: 按需读取指定记忆的完整正文与细节。
6. `handoff_create`: 会话收尾与交接。

### Advanced Profile (全量 21+ 工具)
用于管理员深度维护与复杂分析：
`project_create`, `project_list`, `project_memory_get`, `project_memory_update`, `project_memory_validate`, `project_memory_rebuild`, `memory_get_related`, `memory_update`, `memory_supersede`, `memory_archive`, `handoff_get`, `index_rebuild`, `project_validate`, `paper_evidence_inventory`, `paper_evidence_coverage` 等。

---

## 7. 快速开始与命令行使用

### 安装

```bash
uv sync --extra dev
```

### CLI 命令

```bash
# 1. 触发 Context Compaction Hook
uv run researchos hook session-start --project seismic-ssl
uv run researchos hook post-compaction --project seismic-ssl

# 2. 构建指定层级的上下文
uv run researchos context build seismic-ssl --mode quick
uv run researchos context build seismic-ssl --mode task --task "evaluate ViT SNR"
uv run researchos context build seismic-ssl --mode paper --section experiments

# 3. 运行无损迁移脚本 (v2 -> v3)
uv run researchos migrate --dry-run
uv run researchos migrate
```

### 启动 MCP Server

```bash
# 默认 Lite 模式 (6 工具)
uv run researchos-mcp --transport stdio

# Advanced 模式 (21+ 工具)
RESEARCHOS_PROFILE=advanced uv run researchos-mcp --transport stdio

# SSE 模式
uv run researchos-mcp --transport sse --port 8000
```

---

## 8. 无损迁移指南 (Migration)

ResearchOS 提供全自动化无损迁移工具：
- **安全备份**: 自动在 `.researchos/backups/pre_v3_migration_<timestamp>/` 存储完整快照。
- **100% 记忆保留**: 自动保留全部历史记忆 ID 与关联，保留自定义注释块。
- **自动回滚**: 迁移异常时自动原子回滚至备份状态。

```bash
# 模拟运行
python scripts/migrate_v2_to_v3.py --dry-run

# 执行迁移
python scripts/migrate_v2_to_v3.py
```

---

## 9. 许可证

MIT License.
