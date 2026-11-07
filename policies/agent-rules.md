# Agent Rules of Engagement for ResearchOS

ResearchOS provides an autonomous, long-term memory substrate for multiple agents (Claude, Codex, Gemini, Cursor, and custom tools).

## 1. Project Isolation Principle
- Every project resides in its own isolated directory (`ResearchVault/<project_id>/`).
- Agents must operate strictly within the target project scope. Cross-project searches should only be executed when explicitly requested by human researchers or agents.

## 2. Re-hydration on Entry
- When entering a project, the Agent MUST call `context_build` (or the `memory-context` skill) in `quick` mode or with the current `task` focus to retrieve `PROJECT.md`, `STATE.md`, latest `HANDOFF.md`, and relevant memories.
- Never guess or proceed on ungrounded assumptions when authoritative state is available in the vault.

## 3. Shift Conclusion & Handoff
- Before terminating a session or handing control back to the user or incoming agent, call `handoff_create` to summarize progress, blockers, and next steps.
- This synchronizes `HANDOFF.md` and `STATE.md` for the next agent session.
