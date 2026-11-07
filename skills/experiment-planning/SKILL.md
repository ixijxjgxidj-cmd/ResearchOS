---
name: experiment-planning
description: Rigorous hypothesis formulation, experimental design, and preflight validation before code execution.
---

# Experiment Planning Skill

## Purpose
Prevents wasted compute and ungrounded execution by designing experiments thoroughly in advance, defining clear success criteria and hypotheses, checking negative results from prior experiments, and enforcing preflight validation.

## Step-by-Step Procedure

1. **Review Context & Historical Evidence**:
   - Inspect existing experiments under the project.
   - Specifically check for any prior experiments with `outcome: negative` or `outcome: failed`. Never re-run a previously failed setup without addressing the known root cause.

2. **Draft the Experiment Plan**:
   - Call `research_experiment_create` with:
     - `project_id`: Target project ID.
     - `title`: Descriptive title of the experiment.
     - `research_question`: Exact question this experiment answers.
     - `hypothesis`: Testable scientific hypothesis.
     - `rationale`: Why this approach is expected to work.
     - `literature`: Array of supporting Paper IDs from `01-Literature`.
     - `method`: Concrete steps and algorithm to be executed.
     - `planned_parameters`: Exact hyperparameters, seeds, batch sizes, models planned.
     - `expected_result`: Quantitative or qualitative outcome expected.
     - `success_criteria`: Concrete thresholds (e.g. `["Accuracy >= 85%", "Latency < 50ms"]`).
     - `is_exploratory`: Set to `True` only for exploratory experiments with incomplete initial specifications.

3. **Populate Storage & Execution Details**:
   - In the generated `00-Projects/{PRJ-ID}/Experiments/{EXP-ID}.md`:
     - Under `## 5. Where`: Specify whether this runs locally or on remote GPU servers via the gpu-server-management skill (leveraging Dataset Affinity routing if datasets are pre-cached).
     - Under `## 6. Storage`: Design the directory path where raw artifacts and checkpoints will be saved.

4. **Run Preflight Validation**:
   - Call `research_experiment_validate(experiment_id=EXP_ID)`.
   - If preflight fails, fix missing hypothesis, method, success criteria, or planned parameters.
   - Once preflight passes, update the experiment status to `ready` via `research_experiment_update(experiment_id, {"status": "ready"})`.
