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

**A Universal Long-Term Memory Infrastructure for Autonomous Research Agents**

ResearchOS 是一个 **Agent-independent、Skill-independent、Project-isolated、Markdown-first** 的长期科研记忆系统。

它不是科研管理平台、实验执行引擎或 GPU 调度中心，而是所有科研 Agent（Claude Code, OpenAI Codex, Gemini CLI, Cursor, OpenCode 等）与专业 Skill 共享的通用长期科研记忆底座。

---

## 1. 核心设计原则

1. **One Project, One Folder**: 每个科研项目拥有完全独立的文件夹 (`ResearchVault/<project_id>/`)。
2. **Project Isolation**: 不同项目默认完全隔离，杜绝跨项目记忆污染。
3. **Markdown First**: 普通 Markdown 文件是唯一权威数据源。
4. **Filesystem First**: 本地文件系统存储，不依赖任何关系型数据库或向量数据库。
5. **Agent Independent**: 不绑定任何特定 Agent SDK 或私有 API。
6. **Skill Independent**: 不承担实验规划、代码执行、GPU 管理等专业工作，只提供记忆存储与检索。
7. **Obsidian Optional**: Obsidian 仅作为可选的本地浏览工具，绝不产生插件依赖或专有语法。
8. **Portable**: 整个项目文件夹可直接复制、跨设备迁移、备份并立即生效。
9. **Shared Memory**: 同一项目的所有 Agent 共享同一套记忆。
10. **Human Readable**: 人类可以直接在任何文本编辑器中阅读和修改所有记忆。

---

## 2. 目录结构

```text
ResearchVault/
└── my-research-project/
    ├── PROJECT.md          # 项目元数据与核心目标
    ├── STATE.md            # 当前研究状态、已知事实与进展
    ├── MEMORY.md           # 常驻项目记忆摘要 (Always-on Project Memory, ~2,000 tokens)
    ├── INDEX.md            # 自动生成的记忆分类索引与关联目录
    ├── HANDOFF.md          # 最新一次 Agent 交接摘要
    │
    ├── knowledge/          # 知识与经验 (knowledge)
    ├── decisions/          # 重要科研与架构决策及其原因 (decision)
    ├── hypotheses/         # 假设及其验证状态 (hypothesis)
    ├── observations/       # 实验观察、实测指标与发现 (observation)
    ├── negative/           # 已验证无效的方案与死胡同 (negative)
    ├── references/         # 外部论文 DOI、数据位置、代码引用 (reference)
    ├── handoffs/           # 历史交接记录 (handoff)
    └── archive/            # 归档记忆 (archive)
```

---

## 3. 通用记忆模型

统一使用标准 YAML Frontmatter + Markdown Body：

```yaml
---
id: MEM-2026-0001
project_id: deep-residual-scaling
type: observation
title: Optimal Depth-to-Width Ratio on 7B Frontier is 1:3.2
created_at: 2026-11-08T00:00:00+08:00
updated_at: 2026-11-08T00:00:00+08:00
status: active
source_type: experiment
source_agent: codex
source_skill: experiment-execution
source_ref: RUN-042
confidence: 0.94
tags:
  - scaling-laws
  - frontier
related:
  - MEM-2026-0002
supersedes: null
superseded_by: null
# 论文写作与实验元数据 (可选)
experiment_id: EXP-DEPTH-WIDTH
paper_section: experiments
metrics_summary:
  best_loss: 1.42
  throughput: 3200
parent_experiment: EXP-DEPTH-BASELINE
artifact_paths:
  - artifacts/run_042_loss.png
---

# Optimal Depth-to-Width Ratio on 7B Frontier is 1:3.2

详细的实验结果、指标对比与推导过程...
```

---

## 4. 快速开始

### 安装

```bash
uv sync --extra dev
```

### CLI 命令

```bash
# 1. 创建独立项目
uv run researchos project create "Deep Residual Scaling" --id deep-scaling --goal "Optimize depth vs width"

# 2. 记录记忆
uv run researchos memory add deep-scaling --type observation --title "Frontier optimal at 48L" --content "Details..." --tag scaling

# 3. 搜索记忆 (默认项目隔离)
uv run researchos memory search deep-scaling --query "Frontier"

# 4. 构建 Agent 上下文 (遵守 Token 预算，标注来源路径)
uv run researchos context build deep-scaling --mode task --task "Optimize architecture" --max-tokens 4000

# 5. 记录交接班 (自动同步 HANDOFF.md 与 STATE.md)
uv run researchos handoff create deep-scaling --task "Grid ablation" --progress "Completed 12 runs" --agent codex

# 6. 常驻项目记忆 (Always-on Project Memory)
uv run researchos project memory get deep-scaling
uv run researchos project memory validate deep-scaling

# 7. 论文写作模式 (Paper Writing Mode)
uv run researchos paper inventory deep-scaling --section methodology
uv run researchos paper coverage deep-scaling --section methodology --loaded MEM-2026-0001
```

### 启动 MCP Server

```bash
uv run researchos-mcp --transport stdio
# 或 SSE 模式
uv run researchos-mcp --transport sse --port 8000
```

### Docker 容器部署与持久化

```bash
# 使用 docker-compose 启动带深层健康检查的 SSE MCP 服务
docker compose up -d

# 健康检查探测
curl http://localhost:8000/health
```

### 核心环境变量

| 变量名 | 兼容替代名称 | 默认值 | 作用说明 |
| :--- | :--- | :--- | :--- |
| `RESEARCH_VAULT_ROOT` | `VAULT_PATH` | `./ResearchVault` | 科研记忆存储根目录 |
| `MCP_TRANSPORT` | - | `stdio` (容器默认 `sse`) | MCP 协议传输通道 (`stdio` 或 `sse`) |
| `PORT` | `MCP_PORT` | `8000` | MCP SSE 服务监听端口 |
| `MCP_HOST` | `HOST` | `0.0.0.0` | MCP 绑定监听地址 |
| `LOG_LEVEL` | - | `INFO` | 日志详细级别 (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## 5. MCP 工具列表

| 模块 | 工具名称 | 核心功能 |
| :--- | :--- | :--- |
| **Project** | `project_create` | 幂等创建独立科研项目文件夹与标准文档（自动初始化 `MEMORY.md`） |
| | `project_list` | 列出当前 Vault 中的所有科研项目 |
| | `project_get` | 获取项目元信息、最新状态及交接摘要 |
| **Always-on Memory** | `project_memory_get` | 读取项目常驻记忆 `MEMORY.md` |
| | `project_memory_update` | 原子安全更新 `MEMORY.md` 摘要内容 |
| | `project_memory_validate` | 校验 10 大标准章节结构、记忆 ID 引用真实性与 Token 预算 |
| | `project_memory_rebuild` | 灾难恢复：从底层详细记忆全量重建标准 `MEMORY.md` |
| **Memory** | `memory_add` | 原子写入通用记忆（知识、决策、假设、观察、负面经验、引用，支持实验元数据） |
| | `memory_get` | 根据记忆 ID 读取完整记忆文件（按需展开指标与细节） |
| | `memory_search` | BM25 相关性排序、中英文 N-gram 分词与多维过滤（严格项目隔离） |
| | `memory_get_related` | 关联记忆图谱遍历（related, supersedes, superseded_by，深度与防环控制） |
| | `memory_update` | 原地安全更新记忆属性与正文（含敏感数据扫描与版本保护） |
| | `memory_supersede` | 原子事务替换旧记忆，双向关联指针与异常自动回滚保护 |
| | `memory_archive` | 归档记忆至 `archive/` 目录 |
| **Paper Mode** | `paper_evidence_inventory` | 论文写作全局实验清单（元数据概览，细化完成/失败/中断/运行状态） |
| | `paper_evidence_coverage` | 论文章节证据覆盖度审计（识别已加载、待查与缺失物理产物） |
| **Context** | `context_build` | 按优先级与 Token 预算生成上下文包（Quick 模式默认置顶 `MEMORY.md`） |
| **Handoff** | `handoff_create` | 记录 Agent 交接班，归档记录并同步更新 `HANDOFF.md` 与 `STATE.md` |
| | `handoff_get` | 读取最新 `HANDOFF.md` 交接备忘录 |
| **Maintenance** | `index_rebuild` | 磁盘扫描全量重建 `INDEX.md` 索引目录 |
| | `project_validate` | 校验项目内所有记忆文件的 Schema、相对链接与跨文件关联健康度 |

---

## 6. 从旧版 v1 迁移

提供全自动化迁移脚本：
- **默认 Dry-run**: 绝不擅自修改磁盘文件。
- **自动备份**: 执行前自动创建快照备份。
- **无损转换**: 将旧版 Experiments, Runs, Findings, Claims, Papers, Decisions, Artifacts 转换为 Universal Memory。
- **绝不删除**: 保留原始历史文件。

```bash
# 模拟运行
uv run python scripts/migrate_v1_to_v2.py --vault .

# 实际执行
uv run python scripts/migrate_v1_to_v2.py --vault . --apply
```

---

## 7. 许可证

MIT License.
