# ResearchOS Memory Workflow Guide

ResearchOS acts as the universal shared memory substrate across distinct research agents and skills.

```mermaid
sequenceDiagram
    autonumber
    actor User as Researcher
    participant Agent as Research Agent
    participant MCP as ResearchOS MCP / CLI
    participant Memory as ResearchVault (<project_id>)
    participant Skill as External Scientific Skill

    User->>Agent: "Explore FP8 quantization on LLaMA-3"
    Agent->>MCP: context_build(project_id="llama3-quant", task="FP8")
    MCP->>Memory: Read PROJECT.md, STATE.md, HANDOFF.md, negative/
    Memory-->>MCP: Context Pack
    MCP-->>Agent: Token-budgeted context pack with source file references
    Agent->>Skill: Run FP8 calibration experiment
    Skill-->>Agent: Result: Diverges on LayerNorm; Succeeds with FP32 norm
    Agent->>MCP: memory_add(type="negative", title="FP8 LayerNorm Divergence")
    MCP->>Memory: Write negative/MEM-2026-0001.md & update INDEX.md
    Agent->>MCP: memory_add(type="observation", title="Hybrid FP8/FP32 Convergence")
    MCP->>Memory: Write observations/MEM-2026-0002.md & update INDEX.md
    Agent->>MCP: handoff_create(task="FP8 calibration", progress="Hybrid norm validated")
    MCP->>Memory: Update HANDOFF.md & STATE.md
    Agent-->>User: "Completed calibration and recorded findings into vault."
```

---

## Workflow Steps

1. **Project Setup**:
   Create a project directory using `project_create`.
2. **Context Ingestion**:
   At session start, retrieve distilled context via `context_build`.
3. **External Task Execution**:
   External skills handle GPU scheduling, training, literature analysis, etc.
4. **Memory Recording**:
   Agent calls `memory_add` to commit observations, decisions, hypotheses, negative lessons, and references.
5. **Memory Revision**:
   When new data contradicts older findings, agent calls `memory_supersede`.
6. **Agent Shift Transition**:
   Agent calls `handoff_create` to preserve state for the next session.
