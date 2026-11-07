---
name: literature-review
description: Protocol for discovering, parsing, and documenting scientific literature notes without hallucination.
---

# Literature Review Skill

## Purpose
Establishes a rigorous, Zotero-free workflow for ingesting papers into the ResearchVault as structured markdown notes, linking them directly to experiments and projects while separating author claims from agent interpretations.

## Core Rules
- **No Hallucinated Citations**: Never invent DOIs, author names, years, or quotes. If a field cannot be verified, set it to `null`.
- **Author Claims vs. Agent Inferences**: Keep direct quotes in `## Important Quotes` with section/page numbers. Place your own deductions strictly in `## Agent Interpretation` and `## Relevance to Our Research`.
- **Self-Contained Storage**: Markdown records reside in `01-Literature/{PAPER-ID}.md`. Original PDFs may reside locally or remotely.

## Step-by-Step Procedure

1. **Search Existing Literature**:
   - Call `research_paper_search(query=...)` to check if the paper or topic is already indexed in the vault.

2. **Ingest Paper Record**:
   - Call `research_paper_create` with:
     - `title`: Exact title of the paper.
     - `citekey`: Unique BibTeX key (e.g. `vaswani2017attention`).
     - `authors`: Full author list.
     - `year`: Publication year.
     - `doi`: Digital Object Identifier (if known).
     - `url`: Official paper URL or arXiv link.
     - `abstract`: Verbatim abstract.
     - `projects`: Target Project IDs.
     - `related_experiments`: Experiment IDs benefiting from this literature.

3. **Annotate & Extract Key Insights**:
   - Open the generated `01-Literature/PAPER-YYYY-NNN.md` file.
   - Record:
     - `Methodology`: What algorithm or empirical setup was used?
     - `Main Findings`: What did the authors demonstrate?
     - `Limitations`: What edge cases or failures did the authors acknowledge?
     - `Page References`: Where can key formulas or claims be found in the PDF?

4. **Update Reading Status**:
   - Update `reading_status` from `to_read` to `reading`, `read`, or `synthesized`.
