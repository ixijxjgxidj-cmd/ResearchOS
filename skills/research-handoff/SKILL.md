---
name: research-handoff
description: Inter-agent context consolidation and handoff protocol prior to closing a session.
---

# Research Handoff Skill

## Purpose
Ensures that whenever an Agent session concludes, the next Agent (which may run on a different LLM or machine days later) can resume work seamlessly without needing access to historical chat logs.

## Step-by-Step Procedure

1. **Verify State Consistency**:
   - Ensure all completed Runs have their actual parameters and outcomes backfilled.
   - Ensure newly generated files or plots are registered as Artifacts.

2. **Run Integrity Audit**:
   - Call `research_audit(project_id=PRJ_ID)`.
   - Ensure there are no unreferenced artifacts, broken links, or syntax corruptions.

3. **Update Handoff & Status Documents**:
   - Call `research_handoff_update`:
     - `project_id`: Current project ID.
     - `current_focus`: One-line summary of what you were doing.
     - `completed_since_last`: Bullet points of completed tasks/experiments.
     - `modified_files`: List of files modified during this session.
     - `open_issues`: Active blockers, failing tests, or unverified claims.
     - `next_steps`: Ordered list of actionable tasks for the incoming agent.
     - `target_files_for_next_agent`: Paths of files the next agent should read first.

4. **Regenerate Global Dashboards**:
   - Ensure `99-Dashboard/Projects.md`, `Pending-Experiments.md`, and `Research-Audit.md` are up to date.

5. **Summarize for Human User**:
   - Present a concise, bulleted completion summary to the user referencing the updated `HANDOFF.md`.
