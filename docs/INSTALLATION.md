# ResearchOS Installation & Quickstart Guide

## Prerequisites
- **Python**: `>= 3.11` (Python 3.12 or 3.13 recommended)
- **uv**: Fast Python package installer (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Git**: Installed and available in PATH.

---

## 1. Installation

Clone the repository and synchronize the environment:

```bash
git clone <repository_url> ResearchOS
cd ResearchOS

# Install dependencies and develop mode using uv
uv sync --extra dev
```

---

## 2. Setting Up a ResearchVault

A ResearchVault is any directory on your filesystem where your Markdown files live.

```bash
# Initialize vault in current directory
uv run research init

# Or initialize in an explicit directory
uv run research init --vault /path/to/my_vault
```

---

## 3. Configuring MCP for Claude Code, Codex, Cursor, or Antigravity

Add ResearchOS MCP to your Agent or IDE config file (`claude_desktop_config.json`, `settings.json`, etc.):

```json
{
  "mcpServers": {
    "researchos": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/ResearchOS",
        "run",
        "researchos-mcp"
      ],
      "env": {
        "RESEARCH_VAULT_ROOT": "/path/to/my_vault"
      }
    }
  }
}
```

---

## 4. Running the Test Suite

```bash
uv run pytest -v
```
