# ResearchOS Memory Hooks Installation & Configuration Guide

ResearchOS Memory Hooks provide automated, agent-independent context recovery across session boundaries and context compaction events.

---

## 1. Quick Start with CLI

You can manually trigger or script hooks using the `researchos hook` command group:

```bash
# Event A: Session Start
researchos hook session-start --project seismic-ssl --agent claude-code

# Event B: Pre-Compaction (Save Volatile State)
researchos hook pre-compaction --project seismic-ssl --task "Training ViT 50 epochs" --completed "Baseline eval" --blocker "VRAM limit"

# Event C: Post-Compaction (Restore Working Memory)
researchos hook post-compaction --project seismic-ssl

# Event D: Session End (Create Handoff)
researchos hook session-end --project seismic-ssl --task "Completed initial sweep" --completed "Exported weights" --next "Run ablations"
```

Add `--json` to any command for structured JSON output suitable for automated pipelines:
```bash
researchos hook post-compaction --project seismic-ssl --json
```

---

## 2. Configuring Claude Code

Claude Code supports lifecycle hooks configured in your global or project `.claude/config.json` or `.claude/hooks.json`.

Add the following hook definitions to enable automatic compaction recovery:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "command": "researchos hook run session_start --agent claude_code --json"
      }
    ],
    "PreCompact": [
      {
        "command": "researchos hook run pre_compaction --agent claude_code --json"
      }
    ],
    "PostCompact": [
      {
        "command": "researchos hook run post_compaction --agent claude_code --json"
      }
    ],
    "SessionEnd": [
      {
        "command": "researchos hook run session_end --agent claude_code --json"
      }
    ]
  }
}
```

When `PostCompact` triggers, the ResearchOS adapter returns `additionalContext` containing the restored 4-section `MEMORY.md`, ensuring the compacted session immediately regains complete project orientation.

---

## 3. Configuring Google Antigravity & Gemini CLI

In Google Antigravity, ResearchOS integrates via the Universal ResearchOS MCP server and behavioral rules in `AGENTS.md`.

For automatic post-compaction recovery, ensure your project workspace includes the `AGENTS.md` protocol. When a compaction summary is triggered:
1. The Antigravity agent executes `context_build` in `quick` mode to re-hydrate the L0 `MEMORY.md` context.
2. Or configure a lifecycle rule in `.gemini/antigravity/rules/` to execute `researchos hook post-compaction` upon session resumption.

---

## 4. Python SDK Integration

To integrate hooks directly in custom agent pipelines or Python wrappers:

```python
from researchos.hooks.core import MemoryHookCore
from researchos.hooks.adapters.claude_code import ClaudeCodeAdapter

core = MemoryHookCore(vault_root="./ResearchVault")

# 1. Trigger session start
result = core.on_session_start(project_id="seismic-ssl", agent_id="my-agent")
if result.success:
    print("Injected context:", result.context_text)

# 2. Trigger pre-compaction
core.on_pre_compaction(
    project_id="seismic-ssl",
    agent_id="my-agent",
    task="Hyperparameter Tuning",
    completed_work=["Grid search 10 runs"],
    next_steps=["Analyze loss surfaces"],
)

# 3. Trigger post-compaction
recovery_result = core.on_post_compaction(project_id="seismic-ssl")
print("Restored memory snapshot:", recovery_result.context_text)
```

---

## 5. Strict Project Resolution (Zero Guessing)

The `ProjectResolver` enforces deterministic project discovery:

1. **Explicit Parameter**: `--project <id>` or Python `project_id="<id>"`
2. **Environment Variable**: `RESEARCHOS_PROJECT_ID` or `PROJECT_ID`
3. **Directory Hierarchy**: Traverses upward from the working directory until `PROJECT.md` or `.researchos` is located
4. **Failure Behavior**: If no project can be deterministically resolved, raises `ProjectResolutionError` with actionable remediation guidance. Never guesses or picks arbitrary projects from the vault.
