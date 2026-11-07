---
name: manuscript-writing
description: Traceable, evidence-backed scientific writing and claim verification for papers and technical reports.
---

# Manuscript Writing Skill

## Purpose
Guides the drafting of conference or journal manuscripts, technical reports, and thesis chapters by anchoring every claim directly to empirical runs, figures, negative controls, and literature citations.

## Golden Rules
- **No Unbacked Claims**: Every assertion in the manuscript must link to a `CLAIM-YYYY-NNN` that references concrete `RUN-YYYY-NNN` or `ART-YYYY-NNN`.
- **Negative Results in Discussions**: Negative outcomes must not be concealed; they belong in the Discussion or Limitation sections to demonstrate robustness and scientific rigor.
- **Hypotheses vs Facts**: Speculation or theoretical inferences must be explicitly phrased as hypotheses, not proven facts.

## Step-by-Step Procedure

1. **Load Project Knowledge Pack**:
   - Call `research_context_build(target_id=PRJ_ID)`.
   - Inspect all completed experiments, verified findings, registered literature, and figures.

2. **Formulate or Verify Claims**:
   - Call `research_claim_create` for each primary argument of the paper:
     - `text`: Formal scientific proposition.
     - `status`: `"supported"`, `"unverified"`, or `"partially_supported"`.
     - `supporting_experiments`: List of `EXP-ID`s.
     - `supporting_runs`: List of `RUN-ID`s.
     - `contradicting_experiments`: Prior experiments that failed or showed boundary limits.
     - `artifacts`: Figures, tables, or checkpoint paths.
     - `limitations`: Assumptions under which the claim holds.
     - `manuscript_section`: Target section (e.g. "Section 4.2 Ablation Study").

3. **Drafting Content**:
   - Write sections citing relative Markdown links or BibTeX keys from `01-Literature`.
   - Embed figures via their verified artifact paths.

4. **Audit Claims & Integrity**:
   - Call `research_audit(project_id=PRJ_ID)`.
   - Confirm that no `supported` claims lack empirical backing, and that all negative experiments are properly accounted for in limitations or boundaries.
