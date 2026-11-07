# ResearchOS

**面向多 Agent 科研工作流的持久化记忆、实验管理与证据追溯框架**

ResearchOS 是一个与 Agent、模型、笔记软件和服务器管理工具无关的独立科研管理框架。它的目标是使多个不同的 Agent（如 Claude Code, Codex, Gemini 等）、多个会话、多个实验环境能够共享同一套长期科研记忆。

## 核心原则

- **Markdown-first**: 所有科研知识和科研记录以普通 Markdown 文件保存，配备标准 YAML Frontmatter 与相对链接。
- **Filesystem-first**: 文件系统是唯一权威数据源。即使 ResearchOS 程序被删除，只要 Markdown 文件在，任何 Markdown 编辑器都能阅读。
- **Agent-independent**: 兼容 Claude Code, Codex, Gemini CLI, Cursor, OpenCode 等各类 Agent，统一提供 MCP Server 与 CLI 接口。
- **Obsidian-optional**: Obsidian 仅作为可选的可视化查看器，不依赖任何第三方插件或专有语法。
- **No Zotero Dependency**: 文献以 Paper Markdown 文件自包含管理，PDF 可本地或外链存放，无需额外学术文献管理软件。
- **DSH Infrastructure Reuse**: 与 DSH GPU 服务器基础设施解耦协作，Run 记录服务器元数据与环境指纹，不重复实现底层调度和运维。

## 安装与运行

```bash
# 使用 uv 进行依赖管理与安装
uv sync --extra dev

# CLI 使用
uv run research --help

# 启动 MCP Server
uv run researchos-mcp
```
