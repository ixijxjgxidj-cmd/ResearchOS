---
name: experiment-review
description: Post-run evaluation, metrics extraction, deviation analysis, finding registration, and outcome classification.
---

# Experiment Review Skill

## Purpose
Enforces rigorous post-experiment evaluation. Assesses whether execution succeeded, compares actual parameters against the original plan, registers empirical findings, and classifies scientific outcomes while strictly distinguishing execution failures from disproven hypotheses.

## Crucial Distinction: Failure vs. Negative Outcome
- **Execution Failure (`status: failed`, `outcome: failed`)**: The code crashed, out-of-memory error occurred, network dropped, or dataset path was wrong.
- **Negative Scientific Outcome (`status: completed`, `outcome: negative`)**: The code executed completely and correctly, but the experimental data refuted the original hypothesis. Negative outcomes are vital empirical knowledge and must be preserved!

## Step-by-Step Procedure

1. **Inspect Run Telemetry**:
   - Call `research_run_get(run_id)`.
   - Read execution logs, metrics, and registered artifacts.

2. **Complete the Run**:
   - Call `research_run_complete`:
     - `run_id`: The target Run ID.
     - `actual_parameters`: Exact parameters executed.
     - `status`: `"succeeded"`, `"failed"`, or `"interrupted"`.
     - `metrics`: Dictionary of evaluated metrics (e.g. `{"loss": 0.14, "accuracy": 0.88}`).
     - `deviations`: Any deviations from the original plan.
     - `result_summary`: Concise description of what happened.
     - `experiment_outcome`: Set to `"positive"`, `"negative"`, `"inconclusive"`, or `"failed"`.

3. **Synthesize Findings**:
   - If novel empirical behavior was observed, call `research_finding_create`:
     - `project_id`: Parent project.
     - `experiment_id`: Parent experiment.
     - `run_id`: Originating run.
     - `title`: Concise scientific statement of the finding.
     - `evidence_artifacts`: List of supporting Artifact IDs.
     - `status`: `"verified"` or `"candidate"`.

4. **Update Experiment Markdown**:
   - Review `00-Projects/{PRJ-ID}/Experiments/{EXP-ID}.md`.
   - Complete `## 11. Actual Results`, `## 12. Deviations`, and `## 13. Conclusion`.
   - If all runs are complete and analyzed, transition status from `needs_review` to `completed` via `research_experiment_update`.
