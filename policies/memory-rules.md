# ResearchOS Memory Recording Rules

This policy governs what information should and should not be stored in ResearchOS Universal Memory.

## 1. What to Record

Always record durable, high-value scientific and architectural information:
- **Knowledge (`knowledge`)**: Proven facts, established principles, validated methodologies, and distilled insights.
- **Decisions (`decision`)**: Architectural, methodological, and scientific decisions, with explicit reasons and alternatives considered.
- **Hypotheses (`hypothesis`)**: Testable assertions, expected outcomes, and current status (active, confirmed, rejected).
- **Observations (`observation`)**: Concrete empirical observations, experimental results summaries, and metric benchmarks.
- **Negative Experiences (`negative`)**: Approaches that failed, unviable parameters, negative experimental results, dead ends, and pitfalls. **Negative knowledge is as valuable as positive outcomes.**
- **References (`reference`)**: External links, papers (DOIs), dataset paths, repository commits, and artifact locations.
- **Handoffs (`handoff`)**: Key state transitions between agent shifts.

## 2. What NOT to Record

ResearchOS is NOT a chat log or temporary scratchpad:
- Do NOT dump raw conversation turns or prompt back-and-forth.
- Do NOT store ephemeral intermediate variables or unverified hallucinations.
- Do NOT commit sensitive credentials, API keys, passwords, or SSH keys under any circumstances.
- Do NOT overwrite historical findings when new contradictory evidence arrives; use `memory_supersede` instead.

## 3. Provenance and Traceability

Every memory must specify:
- Source type (`source_type`: `agent`, `human`, `experiment`, `imported`, `system`)
- Originating agent (`source_agent`)
- Calling skill (`source_skill`)
- Provenance identifier (`source_ref`: strongly required for empirical findings, negatives, and decisions)
- Related memories (`related`)
