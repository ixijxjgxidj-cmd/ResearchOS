# ResearchOS Multi-Agent Scientific Workflow Guide

## 1. The Multi-Agent Collaboration Lifecycle

ResearchOS coordinates multiple AI agents across extended temporal horizons through a standard 6-stage lifecycle:

```mermaid
sequenceDiagram
    autonumber
    actor A as Agent A (Planner)
    actor B as Agent B (Executor)
    actor C as Agent C (Writer)
    participant V as ResearchVault (Markdown)
    participant D as DSH (GPU Infrastructure)

    Note over A,V: Phase 1: Problem Formulation & Planning
    A->>V: research_project_create("Sparse Autoencoders")
    A->>V: research_paper_create("Towards Monosemanticity")
    A->>V: research_experiment_create("SAE L1 Lambda Search")
    A->>V: research_experiment_validate (Preflight check)
    A->>V: research_handoff_update ("Design finished, ready for execution")

    Note over B,V: Phase 2: Execution & Infrastructure Lease
    B->>V: research_context_build(EXP_ID)
    B->>D: claim_server(srv_a100_01, duration=120)
    B->>V: research_run_create(EXP_ID, agent="codex", executor="dsh")
    Note over B,D: Runs training in ~/workspace/...
    B->>V: research_artifact_register(RUN_ID, "weights.pt", "checkpoint")
    B->>D: plan_server_backup(srv_a100_01)
    B->>D: release_server(srv_a100_01)
    B->>V: research_run_complete(RUN_ID, actual_params, outcome="positive")
    B->>V: research_finding_create("L1 0.01 yielded 96% alive latents")
    B->>V: research_handoff_update("Execution complete; ready for manuscript")

    Note over C,V: Phase 3: Manuscript Writing & Audit
    C->>V: research_context_build(PRJ_ID)
    C->>V: research_claim_create("SAE features are monosemantic")
    C->>V: research_audit(PRJ_ID)
    C-->>V: Generates paper sections with verified evidence links
```

---

## 2. Preventing Common Multi-Agent Traps

### 2.1 The Context Amnesia Trap
- **Problem**: When a new session begins or context is compressed, agents forget why an experiment was conducted, what previous runs showed, or where checkpoints are.
- **Solution**: Incoming agents always call `research context build <EXP-ID>` to re-hydrate the essential plan, hypothesis, prior runs, deviations, and warnings.

### 2.2 The Silent Overwrite Trap
- **Problem**: Agent B modifies hyperparameters or overwrites files produced by Agent A without leaving an audit trail.
- **Solution**: Optimistic concurrency control via file locking and version checking (`VersionConflictError`), combined with dedicated isolated workspace directories (`~/workspace/{session}_{agent}_{time}`).

### 2.3 The Negative Outcome Suppression Trap
- **Problem**: When a run disproves a hypothesis, agents delete the experiment or falsely label it as a code crash.
- **Solution**: Strict distinction between `status: failed` (code crash) and `outcome: negative` (scientific hypothesis disproven). The `Research-Audit` engine alerts if negative outcomes are unreferenced in limitation sections.
