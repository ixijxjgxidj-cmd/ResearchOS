# ResearchOS Agent Rules & Operational Standards

This document establishes the operational rules for any autonomous agent operating with ResearchOS.

## 1. Context Protocol
- **On Entry**: Run `context_build` in `quick` or `task` mode.
- **Do Not Guess**: Use the information in `PROJECT.md`, `STATE.md`, and `HANDOFF.md`.
- **Cite File Paths**: Attribute statements to their originating Markdown files.

## 2. Universal Memory Hygiene
- **Distill Knowledge**: Do not paste raw chat transcripts. Store synthesized findings, decisions, hypotheses, observations, negative knowledge, or references.
- **Negative Knowledge**: Failed experiments, dead ends, and invalid parameters must be stored as `negative` memories.
- **Supersede Rather Than Delete**: Always use `memory_supersede` to preserve evidence when revising earlier conclusions.

## 3. Shift Conclusion
- **Always Handoff**: Call `handoff_create` before ending a turn or yielding control.
- **Zero Credentials**: Never write API keys, passwords, or tokens into memory files.
