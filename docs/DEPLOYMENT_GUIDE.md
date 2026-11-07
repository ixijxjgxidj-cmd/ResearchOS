# ResearchOS 远程与托管部署指南 (Deployment Guide)

ResearchOS 原生支持作为**远程托管 MCP 服务（Remote MCP Server）**运行，允许多个位于不同物理机器、云端环境、不同客户端（如 Claude Desktop、Cursor、Codex、网页版 Agent 或远程服务器）的 Agent 通过网络同时连接并共享同一套科研长期记忆。

---

## 1. 核心架构约束与部署原则

在考虑托管平台时，必须牢记 ResearchOS 的核心原则：
- **Filesystem-first & Markdown-first**：所有科研知识、实验、Run 记录以普通 Markdown 文件形式存放在磁盘上。
- **持久化存储需求**：托管环境**必须具备持久化磁盘（Persistent Volume）**，或者挂载外部存储卷。否则容器重启时 Markdown 知识库可能会丢失。

---

## 2. 托管方案推荐与实战配置

### 方案 A：容器化云平台（推荐：Railway / Render / Fly.io / Zeabur）

这类平台支持直接从 GitHub 仓库拉取 Dockerfile 构建，并提供持久化卷（Persistent Volume）与自动 HTTPS 域名。

#### 1. Railway 部署步骤
1. 将本项目推送到 GitHub。
2. 登录 [Railway.app](https://railway.app/)，点击 **New Project -> Deploy from GitHub repo**。
3. 在服务设置中：
   - 添加 **Volume**：挂载路径设置为 `/data/vault`。
   - 环境变量添加：
     - `MCP_TRANSPORT=sse`
     - `RESEARCH_VAULT_ROOT=/data/vault`
4. 部署完成后，Railway 会分配一个公开 HTTPS 域名，例如：`https://researchos-production.up.railway.app`。
5. MCP SSE 端点地址即为：`https://researchos-production.up.railway.app/sse`。

---

### 方案 B：独立云服务器 / VPS（Docker & Docker Compose）

适合实验室团队、GPU 服务器节点或企业内网集中部署。

```bash
# 1. 克隆代码
git clone https://github.com/your-org/ResearchOS.git
cd ResearchOS

# 2. 启动 Docker Compose
docker compose up -d
```

服务器将在 `http://0.0.0.0:8000/sse` 启动 SSE 协议服务。
可配合 Nginx 反向代理配置 SSL 证书（HTTPS）。

---

### 方案 C：混合架构：本地 Markdown + Cloudflare Tunnel 穿透（最适合个人科研）

如果你希望**Markdown 文件完全留在自己本地电脑上**（随时用 Obsidian、Typora 或 VS Code 阅读修改），但又想让**云端的 Agent（如网页版 Claude、远程 Codex、服务器上的 Agent）**访问你的 ResearchOS：

1. **本地启动 SSE 服务**：
   ```bash
   uv run python -m researchos.adapters.mcp_server --transport sse --port 8000
   ```

2. **使用 Cloudflare Tunnel 进行公网安全暴露**：
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
   终端会输出一个唯一的免费 HTTPS 链接：`https://random-subdomain.trycloudflare.com/sse`。
3. 任何外部 Agent 只需填入该链接即可无缝连接本地 ResearchVault。

---

### 方案 D：MCP 专用托管注册中心（Smithery.ai / Glama）

- [Smithery.ai](https://smithery.ai/) 是专门的 MCP 托管平台，支持通过 Dockerfile 自动构建。
- 本项目已内置根目录 [Dockerfile](file:///d:/reasearch%20os/Dockerfile)，平台可以直接识别并拉取运行。

---

## 3. 对比：为什么不能像 DSH 一样直接部署到 Cloudflare Workers？

用户的 DSH 基础设施部署在 Cloudflare Workers (`dsh-mcp-server.workers.dev`)：
- **DSH 的特点**：DSH 主要是无状态中继、调度计算，或者将服务器元数据保存在云端 KV / D1 数据库中。
- **ResearchOS 的特点**：坚持 **Markdown-first** 与 **Filesystem-first**。Cloudflare Workers 等纯 Serverless Edge 环境**没有本地持久化 POSIX 文件系统**。
- **如果在 Workers 上部署**：必须重写存储引擎将 Markdown 写入 Cloudflare R2（S3 兼容对象存储）或每次调用 GitHub API 提交 commit。对于需要频繁文件互斥锁、高频局部读写和原子写入的科研实验追踪，**带持久化卷的容器（Railway / VPS / Docker）比纯 Edge Serverless 更快、更稳、更便宜**。

---

## 4. 远程 Agent 客户端配置示例

一旦部署到公网或内网，任何支持 Remote MCP (SSE) 的客户端均可直接接入：

### 4.1 Claude Desktop / Claude Code 配置
在 `claude_desktop_config.json` 中配置：

```json
{
  "mcpServers": {
    "researchos": {
      "url": "https://your-domain.railway.app/sse"
    }
  }
}
```

### 4.2 Cursor / VS Code (Cline / Roo-Code) 配置
在 MCP 设置面板中选择 **SSE** 类型：
- **Name**: `researchos`
- **Type**: `sse`
- **URL**: `https://your-domain.railway.app/sse`

所有连接该端点的 Agent 将实时共享同一份项目规划、实验状态、执行 Run、文献笔记与交接历史！
