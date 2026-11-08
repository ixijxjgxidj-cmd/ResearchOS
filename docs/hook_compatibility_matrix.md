# ResearchOS Context Compaction & Lifecycle Hook Compatibility Matrix

This document provides a technical specification and compatibility analysis for the ResearchOS Memory Hook architecture across major AI Agent runtimes: **Claude Code**, **Google Antigravity / Gemini CLI**, **OpenAI Codex**, and **Generic CLI / Python Runners**.

---

## 1. Matrix Overview

| Agent System | Event A: Session Start | Event B: Pre-Compaction | Event C: Post-Compaction (CORE) | Event D: Session End / Handoff | Fallback Mechanism | Context Injection Route |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Claude Code** | **Native** (`SessionStart`) | **Native** (`PreCompact`) | **Native** (`PostCompact`) | **Native** (`SessionEnd`) | `UserPromptSubmit` prelude injection | `additionalContext` & `systemPromptExtension` |
| **Google Antigravity / Gemini CLI** | **Native** (Session boot hook) | **Supported** (Pre-compaction event) | **Native** (Compaction resume hook) | **Supported** (`/exit` or handoff skill) | Reactive message wakeup & prompt re-hydration | Markdown prompt injection / UI Sidecar |
| **OpenAI Codex** | **Adapter** (Session init hook) | **Adapter** (`pre_request` interceptor) | **Adapter** (Context window overflow recovery) | **Adapter** (Session conclusion) | System prompt re-attachment | `prompt_injection` & parameter enrichment |
| **Generic CLI / Other Agents** | **CLI Tool** (`hook session-start`) | **CLI Tool** (`hook pre-compaction`) | **CLI Tool** (`hook post-compaction`) | **CLI Tool** (`hook session-end`) | Standard output / environment variable dump | Stdout / JSON formatted context packet |

---

## 2. Event Lifecycle Specification

### Event A: Session Start
- **Purpose**: Discovers the active project, validates `MEMORY.md`, recalculates freshness, rebuilds if stale, and injects L0 project memory into the agent context before the first user prompt.
- **Project Boundary Resolution**: Resolved via `ProjectResolver` with strict priority:
  1. Explicit `--project` parameter
  2. `RESEARCHOS_PROJECT_ID` / `PROJECT_ID` environment variables
  3. Upward directory tree search from current working directory (`PROJECT.md` / `.researchos` / `MEMORY.md`)
  4. Explicit projects mapping file
  *Zero guessing*: Ambiguous or unresolvable directories raise a strict `ProjectResolutionError` rather than arbitrarily picking a vault project.

### Event B: Pre-Compaction
- **Purpose**: Triggered immediately before context truncation / summarization takes place. Extracts volatile state, completed subtasks, experimental metrics, and active blockers, updating `STATE.md`, `HANDOFF.md`, and refreshing `MEMORY.md`.
- **Debounce Window**: 1.5-second debounce with unique `event_id` tracking prevents recursive invocation or repeated writes.

### Event C: Post-Compaction (CORE)
- **Purpose**: Triggered immediately after context compaction completes. Re-identifies the target project, validates memory version, rebuilds `MEMORY.md` if necessary, and injects the restored 4-section memory snapshot directly into the newly compressed context window.
- **Guarantee**: True context injection via host runtime mechanisms (e.g., `additionalContext` in Claude Code, system prompt attachment in Antigravity/Gemini, prompt prefix in Codex), rather than merely printing text to terminal.

### Event D: Session End / Handoff
- **Purpose**: Creates an authoritative `HANDOFF.md` entry, updates `STATE.md`, refreshes `MEMORY.md`, and persists progress for the incoming agent.

---

## 3. Host Framework Implementation Details

### Claude Code CLI
- **Adapter**: `researchos.hooks.adapters.claude_code.ClaudeCodeAdapter`
- **Output Format**:
  ```json
  {
    "status": "success",
    "hook": "post_compaction",
    "project_id": "seismic-ssl",
    "project_dir": "/path/to/ResearchVault/seismic-ssl",
    "additionalContext": "# [ResearchOS Context Restored After Compaction]\n...",
    "systemPromptExtension": "..."
  }
  ```
- **Fallback**: If running in older Claude Code environments without native compaction hooks, the adapter supports `handle_user_prompt_fallback`, which checks memory freshness and injects context before processing user prompts.

### Google Antigravity & Gemini CLI
- **Adapter**: `researchos.hooks.adapters.antigravity.GeminiAntigravityAdapter`
- **Output Format**: Clean Markdown string block containing `[!IMPORTANT]` callout and the complete 4-section `MEMORY.md` content.
- **Integration**: Supports native Antigravity skill activation and session wakeup triggers.

### OpenAI Codex & Custom LLM Wrappers
- **Adapter**: `researchos.hooks.adapters.codex.CodexAdapter`
- **Output Format**:
  ```json
  {
    "success": true,
    "event": "post_compaction",
    "project_id": "seismic-ssl",
    "context_text": "# MEMORY\n..."
  }
  ```

### Generic CLI Runner
- **Command**: `researchos hook <event> [--project <id>] [--agent <agent>]`
- **Format Options**: Plain text (default) or `--json` for programmatic integration into arbitrary bash or shell scripts.

---

## 4. Concurrency & Idempotency Safeguards

1. **File Locks**: All hook operations mutate project state under exclusive re-entrant file locks (`.researchos/hook_events.lock`, `.researchos/memory_md.lock`, `.researchos/handoff.lock`).
2. **Idempotency History**: Recent hook events are recorded in `.researchos/hook_events.json` (sliding window of 30 events) to prevent infinite loops during compaction re-runs.
3. **Atomic Writes**: All state mutations use atomic file replacement (`atomic_write_text`), preventing corrupt or half-written markdown files upon process interruption.
