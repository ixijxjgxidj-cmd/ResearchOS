---
name: research-bootstrap
description: Mandatory starting workflow for any agent before executing scientific tasks in ResearchOS.
---

# Research Bootstrap Skill

## Purpose
Enables an incoming Agent (regardless of LLM architecture or session history) to reliably re-hydrate the active project context, understand open problems, check uncompleted experiments, and establish working scope.

## Step-by-Step Procedure

1. **Locate Vault Root & Active Projects**:
   - Run `research_project_list` (or CLI `research project list`).
   - Identify the active target project ID (e.g. `PRJ-2026-001`).

2. **Read High-Level Project State**:
   - Call `research_project_status(project_id)`.
   - Read `PROJECT.md` to review the overarching scientific questions, hypotheses, and scope.
   - Read `STATUS.md` to see recent experiment and run velocity.

3. **Read Latest Agent Handoff**:
   - Inspect `HANDOFF.md` in the project directory.
   - Note:
     - What was the previous agent actively working on?
     - What files were modified?
     - What open blockers or bugs exist?
     - What are the recommended next steps?

4. **Identify Pending Experiments**:
   - Call `research_experiment_list(project_id, status="planned")` or `status="ready"`.
   - If an experiment is assigned to your current task, call `research_context_build(target_id=EXP_ID)` to extract the complete, unified Context Pack.

5. **Establish Task Scope**:
   - Determine whether your task is Literature Review, Experiment Planning, Execution, or Manuscript Writing, and invoke the appropriate corresponding skill.
